const express = require('express');
const router = express.Router();
const bbrScraper = require('../scrapers/basketballReference');
const nbaScraper = require('../scrapers/nbaCom');
const cacheService = require('../services/cacheService');

router.get('/', async (req, res) => {
  try {
    const data = await nbaScraper.getAllPlayers();
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.get('/leaders', async (req, res) => {
  try {
    const { category = 'PTS', season = '2024-25' } = req.query;
    
    let data = await nbaScraper.getLeagueLeaders(category, season);
    
    if (data.error) {
      console.log('Fallback to BBR for leaders');
      data = await bbrScraper.getSeasonLeaders(category, season.replace('-', ''));
    }
    
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.get('/:slug/stats', async (req, res) => {
  try {
    const { slug } = req.params;
    const { season = '2025' } = req.query;
    
    const data = await bbrScraper.getPlayerStats(slug, season);
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.get('/:slug/last-games', async (req, res) => {
  try {
    const { slug } = req.params;
    const { games = 5 } = req.query;
    
    const data = await bbrScraper.getPlayerLastGames(slug, parseInt(games));
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.get('/:slug/props-analysis', async (req, res) => {
  try {
    const { slug } = req.params;
    const { games = 10, prop = 'pts', line = 20.5 } = req.query;
    
    const cacheKey = `props_analysis_${slug}_${prop}_${line}_${games}`;
    const cached = await cacheService.get(cacheKey);
    if (cached) {
      return res.json({ ...cached, fromCache: true });
    }

    const lastGamesData = await bbrScraper.getPlayerLastGames(slug, parseInt(games));
    
    if (lastGamesData.error) {
      return res.status(500).json(lastGamesData);
    }

    const gamesList = lastGamesData.games;
    const lineValue = parseFloat(line);
    const propStat = prop.toLowerCase();
    
    let overs = 0;
    let unders = 0;
    let pushes = 0;
    let totalValue = 0;
    
    const gameLog = gamesList.map(game => {
      const value = game[propStat] || 0;
      const result = value > lineValue ? 'OVER' : value < lineValue ? 'UNDER' : 'PUSH';
      
      if (result === 'OVER') overs++;
      else if (result === 'UNDER') unders++;
      else pushes++;
      
      totalValue += value;
      
      return {
        date: game.date,
        opponent: game.opponent,
        value,
        line: lineValue,
        result,
        diff: parseFloat((value - lineValue).toFixed(2))
      };
    });

    const avg = parseFloat((totalValue / gamesList.length).toFixed(2));
    const overRate = parseFloat(((overs / gamesList.length) * 100).toFixed(1));
    const underRate = parseFloat(((unders / gamesList.length) * 100).toFixed(1));
    
    const last3 = gameLog.slice(0, 3);
    const last3Avg = parseFloat((last3.reduce((a, b) => a + b.value, 0) / 3).toFixed(2));
    const trend = last3Avg > avg ? 'UP' : last3Avg < avg ? 'DOWN' : 'FLAT';
    
    let streak = 0;
    let streakType = '';
    for (let i = 0; i < gameLog.length; i++) {
      if (i === 0 || gameLog[i].result === gameLog[i-1].result) {
        streak++;
        streakType = gameLog[i].result;
      } else {
        break;
      }
    }

    const analysis = {
      player: slug,
      prop: propStat.toUpperCase(),
      line: lineValue,
      sampleSize: gamesList.length,
      averages: {
        overall: avg,
        last3: last3Avg
      },
      record: {
        overs,
        unders,
        pushes,
        overRate,
        underRate
      },
      trend,
      streak: { count: streak, type: streakType },
      recommendation: overRate >= 60 ? 'OVER' : underRate >= 60 ? 'UNDER' : 'NO EDGE',
      confidence: Math.max(overRate, underRate),
      gameLog,
      scrapedAt: new Date().toISOString()
    };

    await cacheService.set(cacheKey, analysis, 60);
    res.json(analysis);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
