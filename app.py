from flask import Flask, render_template_string, request, jsonify
import yfinance as yf
import pandas as pd
import plotly.graph_objs as go
import plotly.io as pio
import datetime
import time
import os
import openai

app = Flask(__name__)

# Define big companies to analyze
COMPANIES = {
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "Amazon": "AMZN",
    "Google": "GOOGL",
    "Tesla": "TSLA"
}

def fetch_stock_data(tickers, max_retries=3, initial_delay=10):
    end_date = datetime.datetime.today()
    start_date = end_date - datetime.timedelta(days=365)
    tries = 0
    delay = initial_delay

    while tries < max_retries:
        try:
            data = yf.download(tickers, start=start_date, end=end_date)
            if data.empty:
                raise ValueError("Empty data received")
            return data
        except Exception as e:
            print(f"Error fetching data: {e}. Retrying after {delay} seconds...")
            time.sleep(delay)
            tries += 1
            delay *= 2
    print(f"Failed to fetch data after {max_retries} retries.")
    return pd.DataFrame()

def analyze_stock(data):
    if data.empty:
        return data
    data['MA20'] = data['Close'].rolling(window=20).mean()
    data['MA50'] = data['Close'].rolling(window=50).mean()
    data['Volatility'] = data['Close'].rolling(window=20).std()
    return data

def generate_plot(data, company_name):
    if data.empty:
        return f"<div style='color:red; text-align:center;'>No data available for {company_name}.</div>"
    traces = []
    if 'Close' in data.columns:
        trace_close = go.Scatter(x=data.index, y=data['Close'], mode='lines', name='Close Price', line=dict(color='cyan'))
        traces.append(trace_close)
    if 'MA20' in data.columns and not data['MA20'].isna().all():
        trace_ma20 = go.Scatter(x=data.index, y=data['MA20'], mode='lines', name='MA20', line=dict(color='orange'))
        traces.append(trace_ma20)
    if 'MA50' in data.columns and not data['MA50'].isna().all():
        trace_ma50 = go.Scatter(x=data.index, y=data['MA50'], mode='lines', name='MA50', line=dict(color='lightgreen'))
        traces.append(trace_ma50)
    if not traces:
        return f"<div style='color:red; text-align:center;'>No valid data available for {company_name}.</div>"
    layout = go.Layout(
        title=f'{company_name} Stock Price and Moving Averages (1 Year)',
        xaxis={'title': 'Date'},
        yaxis={'title': 'Price (USD)'},
        hovermode='x unified',
        plot_bgcolor='#1e1e1e',
        paper_bgcolor='#1e1e1e',
        font=dict(color='#e0e0e0'),
        legend=dict(bgcolor='#1e1e1e')
    )
    fig = go.Figure(data=traces, layout=layout)
    return pio.to_html(fig, full_html=False)

def ai_agent_response_local(text, stocks_info):
    text = text.lower()
    response = "Sorry, I didn't understand the question. Ask about trend, average price, highest or lowest price of a company."
    for company in COMPANIES:
        if company.lower() in text:
            df = stocks_info.get(company)
            if df is None or df.empty:
                return f"No data available for {company}."
            if 'trend' in text:
                recent = df['Close'][-30:]
                if len(recent) < 2:
                    return f"Not enough data to determine trend for {company}."
                diff = recent[-1] - recent[0]
                if diff > 0:
                    return f"The trend for {company} over the last month is upward 📈."
                elif diff < 0:
                    return f"The trend for {company} over the last month is downward 📉."
                else:
                    return f"The trend for {company} over the last month has been flat."
            elif 'average' in text or 'mean' in text:
                avg_price = df['Close'].mean()
                return f"The average closing price of {company} over the past year was ${avg_price:.2f}."
            elif 'highest' in text or 'peak' in text:
                max_price = df['Close'].max()
                date_max = df['Close'].idxmax().date()
                return f"The highest closing price of {company} in the past year was ${max_price:.2f} on {date_max}."
            elif 'lowest' in text or 'dip' in text:
                min_price = df['Close'].min()
                date_min = df['Close'].idxmin().date()
                return f"The lowest closing price of {company} in the past year was ${min_price:.2f} on {date_min}."
            else:
                return "Ask me about the trend, average price, highest or lowest price of the company."
    return response

stocks_data = {}
tickers = [ticker for ticker in COMPANIES.values()]
print(f"Fetching data for {', '.join(tickers)}...")
try:
    raw_data = fetch_stock_data(tickers)

    for company, ticker in COMPANIES.items():
        company_data = pd.DataFrame()
        available_columns = [col[0] for col in raw_data.columns.tolist()]
        standard_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        for column in standard_columns:
            if column in available_columns:
                company_data[column] = raw_data[(column, ticker)]
        if 'Adj Close' in available_columns:
            company_data['Adj Close'] = raw_data[('Adj Close', ticker)]
        if 'Close' not in company_data.columns and 'Adj Close' in company_data.columns:
            company_data['Close'] = company_data['Adj Close']
        analyzed_data = analyze_stock(company_data)
        stocks_data[company] = analyzed_data
except Exception as e:
    print(f"Error processing stock data: {str(e)}")
    for company in COMPANIES:
        stocks_data[company] = pd.DataFrame()

plots_html = {}
for company in COMPANIES:
    plots_html[company] = generate_plot(stocks_data[company], company)

PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Live Stock Dashboard with AI Agent</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: serif;
      background-color: #2e2e2e; /* dark grey background */
      color: rgb(66, 75, 245);   /* blue-ish text color */
    }
    .top-bar {
      background: #1a1a1a;
      padding: 0.75rem 1rem;
      display: flex;
      overflow: hidden; /* Hide overflow */
      white-space: nowrap; /* Prevent line breaks */
      border-bottom: 2px solid #333;
      animation: scroll 20s linear infinite; /* Add animation */
      font-family: serif;
      color: rgb(66, 75, 245);
    }
    @keyframes scroll {
      0% {
          transform: translateX(100%);
      }
      100% {
          transform: translateX(-100%);
      }
    }
    .stock-ticker {
      margin-right: 2rem;
      font-weight: bold;
      color: rgb(66, 75, 245);
      display: inline-block;
    }
    header {
      background: #1f1f1f;
      padding: 1.5rem;
      text-align: center;
      box-shadow: 0 2px 10px rgba(66, 75, 245, 0.6);
      font-family: serif;
      color: rgb(66, 75, 245);
    }
    header h1 {
      margin: 0;
      font-size: 1.8rem;
    }
    .container {
      max-width: 1100px;
      margin: 2rem auto;
      padding: 0 1rem;
      background: #3a3a3a; /* slightly lighter dark grey for container */
      box-shadow: 0 0 15px rgba(66, 75, 245, 0.3);
      border-radius: 10px;
      font-family: serif;
      color: rgb(66, 75, 245);
    }
    .stocks-container {
      display: flex;
      flex-wrap: wrap;
      gap: 1.5rem;
      justify-content: center;
    }
    .stock-card {
      background: #444444; /* medium dark grey */
      padding: 1rem;
      border-radius: 10px;
      flex: 1 1 500px;
      box-shadow: 0 4px 10px rgba(66, 75, 245, 0.5);
      font-family: serif;
      color: rgb(66, 75, 245);
    }
    .stock-title {
      text-align: center;
      font-size: 1.2rem;
      margin-bottom: 1rem;
      color: rgb(66, 75, 245);
    }
    #chat-container {
      margin-top: 3rem;
      padding-top: 2rem;
      border-top: 2px solid rgb(66, 75, 245);
      font-family: serif;
      color: rgb(66, 75, 245);
    }
    #chat-log {
      height: 250px;
      overflow-y: auto;
      background: #3a3a3a;
      padding: 1rem;
      border-radius: 8px;
      border: 1px solid rgb(66, 75, 245);
      margin-bottom: 1rem;
      font-family: serif;
      color: rgb(66, 75, 245);
    }
    .chat-message.user {
      text-align: right;
      color: rgb(66, 75, 245);
    }
    .chat-message.bot {
      text-align: left;
      color: rgb(66, 75, 245);
    }
    #chat-input-container {
      display: flex;
    }
    #chat-input {
      flex: 1;
      padding: 0.75rem 1rem;
      border: 2px solid rgb(66, 75, 245);
      background: #444444;
      color: rgb(66, 75, 245);
      border-right: none;
      border-radius: 8px 0 0 8px;
      outline: none;
      font-family: serif;
    }
    #chat-send-btn {
      padding: 0 2rem;
      background: rgb(66, 75, 245);
      color: white;
      border: none;
      border-radius: 0 8px 8px 0;
      cursor: pointer;
      font-family: serif;
    }
    #chat-send-btn:hover {
      background: rgb(50, 58, 189);
    }
    footer {
      margin: 2rem 0;
      text-align: center;
      color: rgb(180, 180, 180);
      font-family: serif;
    }
  </style>
</head>
<body>
  <div class="top-bar" id="ticker-bar"></div>
  <header>
    <h1>Live Stock Dashboard with AI Agent</h1>
  </header>
  <div class="container">
    <div class="stocks-container">
      {% for company, plot_html in plots_html.items() %}
        <div class="stock-card">
          <div class="stock-title">{{ company }}</div>
          {{ plot_html | safe }}
        </div>
      {% endfor %}
    </div>
    <div id="chat-container">
      <h2>Ask about any stock:</h2>
      <div id="chat-log"></div>
      <div id="chat-input-container">
        <input type="text" id="chat-input" placeholder="e.g., What's the trend for Tesla?" />
        <button id="chat-send-btn">Send</button>
      </div>
    </div>
  </div>
  <footer>
    &copy; 2025 Stock AI Agent.
  </footer>
  <script>
    const chatLog = document.getElementById('chat-log');
    const chatInput = document.getElementById('chat-input');
    const chatSendBtn = document.getElementById('chat-send-btn');

    function appendMessage(message, sender) {
      const div = document.createElement('div');
      div.classList.add('chat-message', sender);
      div.textContent = message;
      chatLog.appendChild(div);
      chatLog.scrollTop = chatLog.scrollHeight;
    }

    async function sendMessage() {
      const text = chatInput.value.trim();
      if (!text) return;
      appendMessage(text, 'user');
      chatInput.value = '';
      appendMessage('Thinking...', 'bot');
      try {
        const response = await fetch('/api/ai', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({message: text})
        });
        const data = await response.json();
        chatLog.lastChild.textContent = data.response;
      } catch {
        chatLog.lastChild.textContent = 'Failed to get a response.';
      }
    }

    chatSendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') sendMessage();
    });

    // Populate top bar with company ticker values (replace with dynamic if needed)
    const tickers = [
      { name: 'Apple', value: 174.56, change: 1.24 },
      { name: 'Microsoft', value: 319.14, change: -0.85 },
      { name: 'Amazon', value: 134.89, change: 0.72 },
      { name: 'Google', value: 123.45, change: -1.12 },
      { name: 'Tesla', value: 263.21, change: 2.57 }
    ];

    const tickerBar = document.getElementById('ticker-bar');
    tickers.forEach(t => {
      const el = document.createElement('div');
      el.className = 'stock-ticker' + (t.change < 0 ? ' down' : '');
      el.textContent = `${t.name}: $${t.value.toFixed(2)} (${t.change > 0 ? '+' : ''}${t.change.toFixed(2)}%)`;
      tickerBar.appendChild(el);
    });
  </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(PAGE_HTML, plots_html=plots_html)

@app.route('/api/ai', methods=['POST'])
def ai_api():
    data = request.json
    message = data.get('message', '')
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    if not openai.api_key:
        print("OpenAI API key not found, using local AI agent")
        response_text = ai_agent_response_local(message, stocks_data)
    else:
        try:
            completion = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful stock market assistant."},
                    {"role": "user", "content": message}
                ],
                max_tokens=300,
                temperature=0.7,
            )
            response_text = completion.choices[0].message['content'].strip()
        except Exception as e:
            print(f"OpenAI API error: {str(e)}")
            response_text = ai_agent_response_local(message, stocks_data)
    return jsonify({'response': response_text})

if __name__ == '__main__':
    app.run(debug=True, port=5005
            )

