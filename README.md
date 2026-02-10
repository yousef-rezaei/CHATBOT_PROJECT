# NORMAN SLE Chatbot 🤖

An intelligent chatbot for the NORMAN Suspect List Exchange (NORMAN-SLE) featuring category-based navigation, smart FAQ matching, and a modern hexagon-themed UI.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Django](https://img.shields.io/badge/django-5.0+-green.svg)

## ✨ Features

- 📖 **Category-based navigation** - 9 FAQ categories with 47 questions
- 🔍 **Smart FAQ matching** - Fuzzy search with confidence scoring
- 💬 **Intelligent responses** - Django-powered backend with FAQ engine
- 🎨 **Modern hexagon UI** - Matching NORMAN website design
- 📱 **Fully responsive** - Works on desktop and mobile
- 🔗 **Related links** - Automatically included in answers

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip
- Git

### Installation

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/norman-chatbot.git
cd norman-chatbot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start server
python manage.py runserver
```

Open http://127.0.0.1:8000

## 📁 Project Structure

```
NORMAN_CHATBOT_PROJECT/
├── chatbot/                 # Main app
│   ├── faq_engine.py       # FAQ matching
│   ├── views.py            # API endpoints
│   ├── data/               # FAQ CSV
│   └── templates/          # HTML
├── config/                 # Settings
├── static/                 # CSS/JS
└── requirements.txt
```

## 🎯 How It Works

1. **Category Selection** - User chooses from 9 categories
2. **Question Selection** - Specific questions appear
3. **Smart Matching** - FAQ engine finds best answer
4. **Response** - Answer with related links

## 🔧 Technologies

- Django 5.0
- Python 3.8+
- Vanilla JavaScript
- CSV data storage

## 📝 License

MIT License

## 🔗 Links

- [NORMAN Network](https://www.norman-network.com/)
- [NORMAN-SLE](https://www.norman-network.com/nds/SLE/)