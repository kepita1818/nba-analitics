const express = require('express');
const router = express.Router();
const bbrScraper = require('../scrapers/basketballReference');
const nbaScraper = require('../scrapers/nbaCom');

router.get('/today', async (req, res) => {
  try {
    let data = await nbaScraper.getSchedule();
    
    if (data.error || !data.games || data.games.length === 0) {
      console.log('Fallback to BBR for games');
      data = await bbrScraper.getTodaysGames();
    }
    
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.get('/schedule', async (req, res) => {
  try {
    const { date } = req.query;
    
    if (date) {
      res.json({ message: 'Busqueda por fecha especifica - en desarrollo', date });
    } else {
      const data = await nbaScraper.getSchedule();
      res.json(data);
    }
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
