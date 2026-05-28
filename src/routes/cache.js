const express = require('express');
const router = express.Router();
const cacheService = require('../services/cacheService');

router.get('/clear', async (req, res) => {
  try {
    await cacheService.clear();
    res.json({ message: 'Cache limpiada completamente' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.get('/clear/:key', async (req, res) => {
  try {
    const { key } = req.params;
    await cacheService.clear(key);
    res.json({ message: `Cache '${key}' limpiada` });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
