const express = require('express');
const cors = require('cors');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

app.get('/', (req, res) => {
  res.json({
    name: 'TipFactory NBA API',
    version: '1.0.0',
    status: 'Running',
    endpoints: {
      players: '/api/players',
      games: '/api/games',
      cache: '/api/cache'
    },
    scrapers: ['Basketball-Reference', 'NBA.com'],
    cache: 'Supabase PostgreSQL'
  });
});

app.get('/health', (req, res) => {
  res.status(200).json({ status: 'healthy', timestamp: new Date().toISOString() });
});

app.use('/api/players', require('./routes/players'));
app.use('/api/games', require('./routes/games'));
app.use('/api/cache', require('./routes/cache'));

app.use((err, req, res, next) => {
  console.error('Error:', err.message);
  res.status(500).json({ error: err.message });
});

app.use((req, res) => {
  res.status(404).json({ error: 'Endpoint no encontrado' });
});

app.listen(PORT, () => {
  console.log(`TipFactory NBA API corriendo en puerto ${PORT}`);
  console.log(`Endpoints disponibles:`);
  console.log(`   GET /api/players`);
  console.log(`   GET /api/players/leaders?category=PTS`);
  console.log(`   GET /api/players/:slug/stats`);
  console.log(`   GET /api/players/:slug/last-games?games=5`);
  console.log(`   GET /api/players/:slug/props-analysis?prop=pts&line=20.5&games=10`);
  console.log(`   GET /api/games/today`);
  console.log(`   GET /api/cache/clear`);
});
