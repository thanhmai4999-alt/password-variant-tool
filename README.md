# 🔑 Password Variant Tool PRO

Multi-Stage Mutation Engine for password variant generation.

**Made with ❤️ by @teddyvrp | v2.0**

## 📋 Features

✅ Multiple transformation rules (12 categories)  
✅ Advanced mutation chains with depth control  
✅ Custom pattern support (prefixes, suffixes, separators)  
✅ Bulk processing with chunking  
✅ Export formats: TXT, CSV, JSON  
✅ Progress tracking & real-time stats  
✅ Web-based UI with responsive design  

## 🏗️ Architecture

```
password-variant-tool/
├── frontend/          (HTML, CSS, JS - Client Side)
├── backend/           (Node.js + Express - Server Side)
├── .gitignore
├── README.md
└── .env.example
```

## 🚀 Quick Start

### Backend Setup

```bash
cd backend
npm install
cp .env.example .env
node server.js
```

Server runs on `http://localhost:3000`

### Frontend Setup

```bash
cd frontend
# Open index.html in browser or serve with:
python -m http.server 8000
# Access: http://localhost:8000
```

## 📝 Rules Categories

1. **Viết thường/hoa/Capitalize** - Case transformations
2. **Thêm số phổ biến** - Common number suffixes
3. **Thêm năm phổ biến** - Year suffixes (1990, 2000, 2024, etc)
4. **Thêm ký tự đặc biệt** - Special characters (@, !, #, $)
5. **Hậu tố kiểu Việt** - Vietnamese-style suffixes (vip, pro, cute, love)
6. **Chuyển sang LEET speak** - Character substitution (a→@, o→0)
7. **Thêm dấu phân cách** - Separators (_, -, .)
8. **Đảo ngược** - Reverse mutations
9. **Nhân đôi & Lặp lại** - Duplication
10. **Từ Username** - Username-based variants
11. **Ghép & Biến đổi** - Concatenation
12. **Biến đổi số điện thoại** - Phone number mutations

## 🔧 API Endpoints

### POST /api/generate

Generate password variants

**Request:**
```json
{
  "data": [
    {"user": "username", "pass": "password123"}
  ],
  "rules": ["1a", "2a", "3a"],
  "depth": 2,
  "mode": "basic",
  "maxResults": 100000
}
```

**Response:**
```json
{
  "success": true,
  "count": 1500,
  "variants": ["password123", ...],
  "ratio": 1.5
}
```

### POST /api/generate/custom

Generate from custom patterns

**Request:**
```json
{
  "data": [{"user": "user", "pass": "pass"}],
  "suffixes": ["123", "vip", "@"],
  "prefixes": ["admin_", "test_"],
  "separators": ["_", "-", "."]
}
```

## 🛡️ Security Features

✅ **Backend Processing** - Logic hidden from client  
✅ **Input Validation** - Sanitize all inputs  
✅ **Rate Limiting** - Prevent abuse  
✅ **Max Length Check** - Prevent oversized variants  
✅ **Entropy Detection** - Filter weak patterns  
✅ **HTTPS Ready** - Support for secure connections  

## ⚙️ Environment Variables

Create `.env` file:

```env
PORT=3000
NODE_ENV=production
MAX_RESULTS=1000000
CHUNK_SIZE=500
RATE_LIMIT=100
```

## 📊 Performance

- Processes large files via chunking
- Async/await for non-blocking operations
- Configurable depth (1-4) for variant mutation
- Max length validation prevents memory bloat

## 🐛 Troubleshooting

**Q: Backend won't start**  
A: Check Node.js version (14+) and PORT not in use

**Q: CORS errors**  
A: Frontend and backend must be on same origin or CORS configured

**Q: Slow processing**  
A: Reduce chunk size or max results limit

## 📄 License

MIT - Feel free to modify and use

## 👨‍💻 Author

@teddyvrp - 2026
