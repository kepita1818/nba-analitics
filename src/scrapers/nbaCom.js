const axios = require('axios');
const cacheService = require('../services/cacheService');

const NBA_API_BASE = 'https://stats.nba.com/stats';

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'application/json, text/plain, */*',
  'Accept-Language': 'en-US,en;q=0.9',
  'Origin': 'https://www.nba.com',
  'Referer': 'https://www.nba.com/'
};

class NbaComScraper {
  
  async getAllPlayers() {
    const cacheKey = 'nba_all_players';
    
    const cached = await cacheService.get(cacheKey);
    if (cached) return cached;

    try {
      const url = `${NBA_API_BASE}/playerindex?LeagueID=00&Season=2024-25`;
      
      const response = await axios.get(url, { 
        headers: HEADERS,
        timeout: 15000 
      });

      const players = response.data.resultSets[0].rowSet.map(row => ({
        id: row[0],
        name: row[2],
        team: row[7],
        teamId: row[6],
        position: row[8],
        height: row[10],
        weight: row[11],
        country: row[12],
        lastAffiliation: row[13],
        birthdate: row[14],
        draftYear: row[22],
        draftRound: row[23],
        draftNumber: row[24],
        fromYear: row[26],
        toYear: row[27]
      }));

      const result = {
        count: players.length,
        players,
        scrapedAt: new Date().toISOString()
      };

      await cacheService.set(cacheKey, result, 1440);
      return result;
    } catch (error) {
      console.error('Error fetching NBA players:', error.message);
      return { error: error.message };
    }
  }

  async getSchedule(days = 7) {
    const today = new Date();
    const cacheKey = `nba_schedule_${today.toISOString().split('T')[0]}`;
    
    const cached = await cacheService.get(cacheKey);
    if (cached) return cached;

    try {
      const gameDate = today.toISOString().split('T')[0];
      
      const url = `${NBA_API_BASE}/scoreboardv2?DayOffset=0&LeagueID=00&gameDate=${gameDate}`;
      
      const response = await axios.get(url, { 
        headers: HEADERS,
        timeout: 15000 
      });

      const games = response.data.resultSets[0].rowSet.map(row => ({
        gameId: row
