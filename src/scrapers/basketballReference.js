const axios = require('axios');
const cheerio = require('cheerio');
const cacheService = require('../services/cacheService');

const BASE_URL = 'https://www.basketball-reference.com';

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
  'Accept-Language': 'en-US,en;q=0.5',
  'Connection': 'keep-alive',
  'Upgrade-Insecure-Requests': '1'
};

class BasketballReferenceScraper {
  
  async getPlayerStats(playerSlug, season = '2026') {
    const cacheKey = `bbr_player_${playerSlug}_${season}`;
    
    const cached = await cacheService.get(cacheKey);
    if (cached) {
      console.log(`Cache hit: ${cacheKey}`);
      return cached;
    }

    try {
      const url = `${BASE_URL}/players/${playerSlug[0]}/${playerSlug}.html`;
      console.log(`Scraping: ${url}`);
      
      const response = await axios.get(url, { 
        headers: HEADERS,
        timeout: 15000,
        maxRedirects: 5
      });

      const $ = cheerio.load(response.data);
      
      const stats = this._extractPerGameStats($, season);
      const advanced = this._extractAdvancedStats($, season);
      
      const result = {
        player: playerSlug,
        season: season,
        perGame: stats,
        advanced: advanced,
        scrapedAt: new Date().toISOString()
      };

      await cacheService.set(cacheKey, result, 120);
      
      return result;
    } catch (error) {
      console.error(`Error scraping ${playerSlug}:`, error.message);
      return { error: error.message, player: playerSlug };
    }
  }

  async getSeasonLeaders(category = 'PTS', season = '') {
    const cacheKey = `bbr_leaders_${category}_${season}`;
    
    const cached = await cacheService.get(cacheKey);
    if (cached) return cached;

    try {
      const url = `${BASE_URL}/leagues/NBA_${season}_per_game.html`;
      
      const response = await axios.get(url, { 
        headers: HEADERS,
        timeout: 15000 
      });

      const $ = cheerio.load(response.data);
      const leaders = [];

      $('table#per_game_stats tbody tr').each((i, el) => {
        if (i >= 50) return false;
        
        const $row = $(el);
        const playerCell = $row.find('td[data-stat="player"]');
        
        if (playerCell.length) {
          leaders.push({
            rank: i + 1,
            player: playerCell.text().trim(),
            team: $row.find('td[data-stat="team_id"]').text().trim(),
            games: parseInt($row.find('td[data-stat="g"]').text()) || 0,
            pts: parseFloat($row.find('td[data-stat="pts_per_g"]').text()) || 0,
            reb: parseFloat($row.find('td[data-stat="trb_per_g"]').text()) || 0,
            ast: parseFloat($row.find('td[data-stat="ast_per_g"]').text()) || 0,
            fgPct: parseFloat($row.find('td[data-stat="fg_pct"]').text()) || 0,
            threePct: parseFloat($row.find('td[data-stat="fg3_pct"]').text()) || 0,
            ftPct: parseFloat($row.find('td[data-stat="ft_pct"]').text()) || 0,
            min: parseFloat($row.find('td[data-stat="mp_per_g"]').text()) || 0,
            slug: playerCell.find('a').attr('href')?.replace('/players/', '').replace('.html', '') || null
          });
        }
      });

      const result = {
        category,
        season,
        leaders,
        scrapedAt: new Date().toISOString()
      };

      await cacheService.set(cacheKey, result, 180);
      return result;
    } catch (error) {
      console.error(`Error scraping leaders:`, error.message);
      return { error: error.message };
    }
  }

  async getTodaysGames() {
    const today = new Date();
    const cacheKey = `bbr_games_${today.toISOString().split('T')[0]}`;
    
    const cached = await cacheService.get(cacheKey);
    if (cached) return cached;

    try {
      const year = today.getFullYear();
      const month = String(today.getMonth() + 1).padStart(2, '0');
      const day = String(today.getDate()).padStart(2, '0');
      
      const url = `${BASE_URL}/boxscores/index.fcgi?month=${month}&day=${day}&year=${year}`;
      
      const response = await axios.get(url, { 
        headers: HEADERS,
        timeout: 15000 
      });

      const $ = cheerio.load(response.data);
      const games = [];

      $('div.game_summary').each((i, el) => {
        const $game = $(el);
        const teams = $game.find('table.teams tr');
        
        if (teams.length >= 2) {
          const awayTeam = $(teams[0]);
          const homeTeam = $(teams[1]);
          
          games.push({
            away: {
              team: awayTeam.find('td:first-child a').text().trim(),
              score: parseInt(awayTeam.find('td:last-child').text()) || null
            },
            home: {
              team: homeTeam.find('td:first-child a').text().trim(),
              score: parseInt(homeTeam.find('td:last-child').text()) || null
            },
            status: $game.find('p.links a').text().includes('Preview') ? 'upcoming' : 'final'
          });
        }
      });

      const result = {
        date: today.toISOString().split('T')[0],
        games,
        scrapedAt: new Date().toISOString()
      };

      await cacheService.set(cacheKey, result, 15);
      return result;
    } catch (error) {
      console.error(`Error scraping games:`, error.message);
      return { error: error.message };
    }
  }

  async getPlayerLastGames(playerSlug, numGames = 5) {
    const cacheKey = `bbr_lastgames_${playerSlug}_${numGames}`;
    
    const cached = await cacheService.get(cacheKey);
    if (cached) return cached;

    try {
      const url = `${BASE_URL}/players/${playerSlug[0]}/${playerSlug}/gamelog/2026`;
      
      const response = await axios.get(url, { 
        headers: HEADERS,
        timeout: 15000 
      });

      const $ = cheerio.load(response.data);
      const games = [];

      $('table#pgl_basic tbody tr').each((i, el) => {
        const $row = $(el);
        if ($row.hasClass('thead')) return;
        
        const gameNum = parseInt($row.find('td[data-stat="ranker"]').text());
        if (!gameNum || gameNum > numGames) return false;

        games.push({
          gameNum,
          date: $row.find('td[data-stat="date_game"]').text().trim(),
          opponent: $row.find('td[data-stat="opp_id"] a').text().trim(),
          result: $row.find('td[data-stat="game_result"]').text().trim(),
          mp: $row.find('td[data-stat="mp"]').text().trim(),
          fg: $row.find('td[data-stat="fg"]').text().trim(),
          fga: $row.find('td[data-stat="fga"]').text().trim(),
          fgPct: parseFloat($row.find('td[data-stat="fg_pct"]').text()) || 0,
          threeP: parseInt($row.find('td[data-stat="fg3"]').text()) || 0,
          threePA: parseInt($row.find('td[data-stat="fg3a"]').text()) || 0,
          threePct: parseFloat($row.find('td[data-stat="fg3_pct"]').text()) || 0,
          ft: parseInt($row.find('td[data-stat="ft"]').text()) || 0,
          fta: parseInt($row.find('td[data-stat="fta"]').text()) || 0,
          ftPct: parseFloat($row.find('td[data-stat="ft_pct"]').text()) || 0,
          orb: parseInt($row.find('td[data-stat="orb"]').text()) || 0,
          drb: parseInt($row.find('td[data-stat="drb"]').text()) || 0,
          trb: parseInt($row.find('td[data-stat="trb"]').text()) || 0,
          ast: parseInt($row.find('td[data-stat="ast"]').text()) || 0,
          stl: parseInt($row.find('td[data-stat="stl"]').text()) || 0,
          blk: parseInt($row.find('td[data-stat="blk"]').text()) || 0,
          tov: parseInt($row.find('td[data-stat="tov"]').text()) || 0,
          pf: parseInt($row.find('td[data-stat="pf"]').text()) || 0,
          pts: parseInt($row.find('td[data-stat="pts"]').text()) || 0,
          plusMinus: $row.find('td[data-stat="plus_minus"]').text().trim()
        });
      });

      const result = {
        player: playerSlug,
        lastGames: numGames,
        games,
        averages: this._calculateAverages(games),
        scrapedAt: new Date().toISOString()
      };

      await cacheService.set(cacheKey, result, 60);
      return result;
    } catch (error) {
      console.error(`Error scraping last games:`, error.message);
      return { error: error.message };
    }
  }

  _extractPerGameStats($, season) {
    const row = $(`table#per_game tbody tr:has(th:contains("${season}-"))`);
    if (!row.length) return null;

    return {
      season: row.find('th').text().trim(),
      age: parseInt(row.find('td[data-stat="age"]').text()) || null,
      team: row.find('td[data-stat="team_id"] a').text().trim(),
      games: parseInt(row.find('td[data-stat="g"]').text()) || 0,
      gs: parseInt(row.find('td[data-stat="gs"]').text()) || 0,
      mp: parseFloat(row.find('td[data-stat="mp_per_g"]').text()) || 0,
      fg: parseFloat(row.find('td[data-stat="fg_per_g"]').text()) || 0,
      fga: parseFloat(row.find('td[data-stat="fga_per_g"]').text()) || 0,
      fgPct: parseFloat(row.find('td[data-stat="fg_pct"]').text()) || 0,
      threeP: parseFloat(row.find('td[data-stat="fg3_per_g"]').text()) || 0,
      threePA: parseFloat(row.find('td[data-stat="fg3a_per_g"]').text()) || 0,
      threePct: parseFloat(row.find('td[data-stat="fg3_pct"]').text()) || 0,
      twoP: parseFloat(row.find('td[data-stat="fg2_per_g"]').text()) || 0,
      twoPA: parseFloat(row.find('td[data-stat="fg2a_per_g"]').text()) || 0,
      twoPct: parseFloat(row.find('td[data-stat="fg2_pct"]').text()) || 0,
      ft: parseFloat(row.find('td[data-stat="ft_per_g"]').text()) || 0,
      fta: parseFloat(row.find('td[data-stat="fta_per_g"]').text()) || 0,
      ftPct: parseFloat(row.find('td[data-stat="ft_pct"]').text()) || 0,
      orb: parseFloat(row.find('td[data-stat="orb_per_g"]').text()) || 0,
      drb: parseFloat(row.find('td[data-stat="drb_per_g"]').text()) || 0,
      trb: parseFloat(row.find('td[data-stat="trb_per_g"]').text()) || 0,
      ast: parseFloat(row.find('td[data-stat="ast_per_g"]').text()) || 0,
      stl: parseFloat(row.find('td[data-stat="stl_per_g"]').text()) || 0,
      blk: parseFloat(row.find('td[data-stat="blk_per_g"]').text()) || 0,
      tov: parseFloat(row.find('td[data-stat="tov_per_g"]').text()) || 0,
      pf: parseFloat(row.find('td[data-stat="pf_per_g"]').text()) || 0,
      pts: parseFloat(row.find('td[data-stat="pts_per_g"]').text()) || 0
    };
  }

  _extractAdvancedStats($, season) {
    const row = $(`table#advanced tbody tr:has(th:contains("${season}-"))`);
    if (!row.length) return null;

    return {
      per: parseFloat(row.find('td[data-stat="per"]').text()) || 0,
      tsPct: parseFloat(row.find('td[data-stat="ts_pct"]').text()) || 0,
      threePAr: parseFloat(row.find('td[data-stat="fg3a_per_fga_pct"]').text()) || 0,
      ftr: parseFloat(row.find('td[data-stat="fta_per_fga_pct"]').text()) || 0,
      orbPct: parseFloat(row.find('td[data-stat="orb_pct"]').text()) || 0,
      drbPct: parseFloat(row.find('td[data-stat="drb_pct"]').text()) || 0,
      trbPct: parseFloat(row.find('td[data-stat="trb_pct"]').text()) || 0,
      astPct: parseFloat(row.find('td[data-stat="ast_pct"]').text()) || 0,
      stlPct: parseFloat(row.find('td[data-stat="stl_pct"]').text()) || 0,
      blkPct: parseFloat(row.find('td[data-stat="blk_pct"]').text()) || 0,
      tovPct: parseFloat(row.find('td[data-stat="tov_pct"]').text()) || 0,
      usgPct: parseFloat(row.find('td[data-stat="usg_pct"]').text()) || 0,
      ows: parseFloat(row.find('td[data-stat="ows"]').text()) || 0,
      dws: parseFloat(row.find('td[data-stat="dws"]').text()) || 0,
      ws: parseFloat(row.find('td[data-stat="ws"]').text()) || 0,
      ws48: parseFloat(row.find('td[data-stat="ws_per_48"]').text()) || 0,
      obpm: parseFloat(row.find('td[data-stat="obpm"]').text()) || 0,
      dbpm: parseFloat(row.find('td[data-stat="dbpm"]').text()) || 0,
      bpm: parseFloat(row.find('td[data-stat="bpm"]').text()) || 0,
      vorp: parseFloat(row.find('td[data-stat="vorp"]').text()) || 0
    };
  }

  _calculateAverages(games) {
    if (!games.length) return null;
    
    const stats = ['pts', 'trb', 'ast', 'stl', 'blk', 'tov', 'fgPct', 'threePct', 'ftPct'];
    const averages = {};
    
    stats.forEach(stat => {
      const sum = games.reduce((acc, g) => acc + (g[stat] || 0), 0);
      averages[stat] = parseFloat((sum / games.length).toFixed(2));
    });
    
    return averages;
  }
}

module.exports = new BasketballReferenceScraper();
