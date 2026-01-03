# Aenigma Verborum
**Web-based Latin-German Vocabulary Trainer with Adaptive Quizzes & Collectible Cards**

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.x-green)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/SQLite-yellow)](https://www.sqlite.org/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES6-orange)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)

## 🎯 Features

| Feature | Description |
|---------|-------------|
| **Personal Vocab Book** | Add/edit/delete Latin words + German translations with word type (Noun/Verb) & flexion info |
| **Adaptive Quizzes** | Multiple choice focusing on weak words (<95% accuracy or <100 attempts) |
| **Verb Sorting Game** | Drag verbs to correct conjugation categories (I, II, III, IV Konjugation) |
| **Performance Tracking** | Real-time accuracy % per word with answer history |
| **Bronze Card System** | Unlock collectible cards at 90%+ accuracy (AI-generated descriptions) |
| **AI Wrong Answers** | OpenAI generates plausible distractors (never true meanings from FragCaesar + DB) |

## 🏗️ Tech Stack

Frontend: Vanilla HTML/CSS/JS + Drag & Drop API
Backend: Flask + SQLAlchemy + SQLite
AI: OpenAI GPT-4.1-mini (wrong answer generation)
Scraping: FragCaesar.de (true German meanings for Latin words)
Deployment: Ready for Render/Heroku/Vercel


## 🚀 Quick Start

```bash
# Clone & install
git clone https://github.com/seb0305/Aenigma-Verborum.git
cd Aenigma-Verborum
pip install -r requirements.txt

# Set OpenAI key
export OPENAI_API_KEY="sk-..."

# Run
flask run
# Visit http://localhost:5000
```

## 🎮 How to Play
1. Build Your Vocab Book

Vocab → Add "amare" (lieben) → Verb → I-Konjugation
Vocab → Add "currere" (laufen) → Verb → III-Konjugation
2. Adaptive Quiz Mode
Focuses on weak words automatically

4 options: 1 correct + 3 AI-generated wrong answers

Tracks accuracy per word

3. Verb Sorting Challenge

Drag "amō, amās, amat" → I-Konjugation
Drag "currō, curris, currit" → III-Konjugation
Answer all verbs once per round → Quiz Complete!
4. Earn Bronze Cards
text
90%+ accuracy → "Bronze card for amare unlocked!"
View collection in Cards tab

## 🧠 Adaptive Algorithm

Weak Word = accuracy < 95% OR total_answers < 100
Quiz prioritizes weakest 10 words
True meanings = DB translation + FragCaesar scrapes
AI distractors = GPT-4.1-mini (filtered: never true meanings)

## 📊 Database Schema

erDiagram
    User ||--o{ VocabEntry : owns
    User ||--o{ QuizRound : "starts"
    QuizRound ||--o{ QuizAnswer : "contains"
    QuizAnswer }o--|| VocabEntry : "rates"
    VocabEntry ||--o{ Card : "unlocks"
    User ||--o{ UserCard : "collects"

## 🔮 Future Roadmap
 Silver/Gold cards (95%/99% accuracy)

 Noun declension sorting game

 Leaderboards & daily challenges

 Image generation for cards (DALL-E 3)

 Mobile PWA support

 Multi-language (Latin-English, Latin-French)

🐛 Known Issues (Fixed)
✅ Infinite verb sorting → QuizAnswer tracking per round
✅ Model column mismatches → quiz_round_id/vocab_entry_id
✅ AI duplicate answers → Strict filtering + retry logic
✅ Bronze card logic → 90% threshold + cleanup

## 📝 Development
```bash
# Add dev dependencies
pip install python-dotenv flask-cors

# Debug mode
flask --debug run

# Test endpoints
curl -X POST http://localhost:5000/api/quiz/verbs/start
curl http://localhost:5000/api/quiz/verbs/next
```

## 🙌 Contributing
Fork & clone

Add Latin verbs to VocabEntry (especially with flexion_type)

Test sorting quiz → Submit PR

Bonus: Improve AI prompts or card designs!

## 📄 License
MIT - Free for educational use!

Built with ❤️ for Latin students
Latin: "Amare et sapere vix deo conceditur"
(Even a god can hardly love and be wise at the same time)