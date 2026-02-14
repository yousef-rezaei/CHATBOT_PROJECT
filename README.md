# FAQ Chatbot

A smart chatbot with category-based navigation and intelligent FAQ matching.

## Features

- Category-based question navigation
- Smart FAQ search with fuzzy matching
- Modern hexagon UI design
- Fully responsive

## Installation

```bash
git clone https://github.com/yousef-rezaei/CHATBOT_PROJECT.git
cd CHATBOT_PROJECT
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Visit `http://127.0.0.1:8000`

## Technologies

- Django 5.0
- Python 3.8+
- JavaScript
- CSS3

## Usage

1. Click a category
2. Select a question
3. Get instant answers

## Adding Content

Edit `chatbot/data/chatbot_faq.csv` and restart the server.

## License

MIT