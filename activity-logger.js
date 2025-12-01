/**
 * Activity Logger for Word Puzzle Games
 * Tracks all user activity across games for analytics and personalization
 */

const ActivityLogger = {
  STORAGE_KEY: 'wordPuzzleGames_activityLog',
  
  /**
   * Get all activity logs from localStorage
   * @returns {Array} Array of activity entries
   */
  getLogs() {
    try {
      const data = localStorage.getItem(this.STORAGE_KEY);
      return data ? JSON.parse(data) : [];
    } catch (e) {
      console.error('Error reading activity log:', e);
      return [];
    }
  },
  
  /**
   * Save logs to localStorage
   * @param {Array} logs - Array of activity entries
   */
  saveLogs(logs) {
    try {
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(logs));
    } catch (e) {
      console.error('Error saving activity log:', e);
    }
  },
  
  /**
   * Add a new activity entry (internal use)
   * @param {Object} entry - Activity entry object
   */
  _addEntry(entry) {
    const logs = this.getLogs();
    const fullEntry = {
      id: Date.now() + '-' + Math.random().toString(36).substr(2, 9),
      timestamp: new Date().toISOString(),
      ...entry
    };
    logs.push(fullEntry);
    this.saveLogs(logs);
    return fullEntry;
  },
  
  /**
   * Log a game session start
   * @param {string} game - Game name (e.g., 'wordle', 'thirdle', 'missing-vowels')
   * @param {Object} details - Additional details (e.g., category, word length)
   * @returns {string} Session ID for tracking
   */
  startSession(game, details = {}) {
    const sessionId = Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    this._addEntry({
      type: 'session_start',
      sessionId,
      game,
      ...details
    });
    return sessionId;
  },
  
  /**
   * Log an event within a session (guess, round_end, etc.)
   * @param {string} sessionId - Session ID from startSession
   * @param {string} eventType - Event type ('guess', 'round_end', etc.)
   * @param {Object} details - Event details
   */
  log(sessionId, eventType, details = {}) {
    this._addEntry({
      type: eventType,
      sessionId,
      ...details
    });
  },
  
  /**
   * Log a game session end (alias for backwards compatibility)
   * @param {string} sessionId - Session ID from startSession
   * @param {string} game - Game name
   * @param {Object} results - Final results (score, won, etc.)
   */
  endSession(sessionId, game, results = {}) {
    this._addEntry({
      type: 'session_end',
      sessionId,
      game,
      ...results
    });
  },
  
  /**
   * Log a user action (alias for backwards compatibility)
   * @param {string} sessionId - Current session ID
   * @param {string} game - Game name
   * @param {string} action - Action type ('guess', 'answer', 'skip', etc.)
   * @param {Object} details - Action details
   */
  logAction(sessionId, game, action, details = {}) {
    this._addEntry({
      type: 'action',
      sessionId,
      game,
      action,
      ...details
    });
  },
  
  /**
   * Get statistics summary
   * @returns {Object} Summary statistics
   */
  getStats() {
    const logs = this.getLogs();
    // Count both session_end (thirdle/wordle) and round_end (other games) as completed sessions
    const sessions = logs.filter(l => l.type === 'session_end' || l.type === 'round_end');
    const startSessions = logs.filter(l => l.type === 'session_start');
    const guesses = logs.filter(l => l.type === 'guess' || l.type === 'action');
    
    const gameStats = {};
    
    // Build game stats from session starts
    startSessions.forEach(session => {
      if (!gameStats[session.game]) {
        gameStats[session.game] = {
          gamesPlayed: 0,
          totalScore: 0,
          wins: 0,
          losses: 0,
          totalReactionTime: 0,
          reactionCount: 0
        };
      }
    });
    
    // Update stats from completed sessions
    sessions.forEach(session => {
      // Find the game name from the session or from the corresponding start
      const game = session.game || startSessions.find(s => s.sessionId === session.sessionId)?.game;
      if (!game) return;
      
      if (!gameStats[game]) {
        gameStats[game] = {
          gamesPlayed: 0,
          totalScore: 0,
          wins: 0,
          losses: 0,
          totalReactionTime: 0,
          reactionCount: 0
        };
      }
      gameStats[game].gamesPlayed++;
      
      // Handle different score field names
      const score = session.score ?? session.guessCount ?? 0;
      if (score !== undefined) {
        gameStats[game].totalScore += score;
      }
      if (session.won === true) {
        gameStats[game].wins++;
      } else if (session.won === false) {
        gameStats[game].losses++;
      }
    });
    
    // Calculate average reaction times from guesses
    guesses.forEach(guess => {
      const game = guess.game || startSessions.find(s => s.sessionId === guess.sessionId)?.game;
      if (!game || !gameStats[game]) return;
      
      const reactionTime = guess.reactionTimeMs ?? guess.reactionTime ?? 0;
      if (reactionTime > 0) {
        gameStats[game].totalReactionTime += reactionTime;
        gameStats[game].reactionCount++;
      }
    });
    
    // Calculate averages
    Object.keys(gameStats).forEach(game => {
      const stats = gameStats[game];
      if (stats.reactionCount > 0) {
        stats.avgReactionTimeMs = Math.round(stats.totalReactionTime / stats.reactionCount);
      }
      // Clean up temp fields
      delete stats.totalReactionTime;
      delete stats.reactionCount;
    });
    
    return {
      totalSessions: sessions.length,
      totalGuesses: guesses.length,
      gameStats,
      firstActivity: logs.length > 0 ? logs[0].timestamp : null,
      lastActivity: logs.length > 0 ? logs[logs.length - 1].timestamp : null
    };
  },
  
  /**
   * Export logs as JSON string
   * @returns {string} JSON string of all logs
   */
  exportLogs() {
    const logs = this.getLogs();
    const stats = this.getStats();
    return JSON.stringify({
      exportedAt: new Date().toISOString(),
      stats,
      logs
    }, null, 2);
  },
  
  /**
   * Export logs as downloadable file
   */
  downloadLogs() {
    const data = this.exportLogs();
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `word-puzzle-activity-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
  
  /**
   * Clear all activity logs
   */
  clearLogs() {
    localStorage.removeItem(this.STORAGE_KEY);
  },
  
  /**
   * Get logs for a specific game
   * @param {string} game - Game name
   * @returns {Array} Filtered logs
   */
  getLogsForGame(game) {
    return this.getLogs().filter(l => l.game === game);
  },
  
  /**
   * Get recent activity (last N entries)
   * @param {number} count - Number of entries to return
   * @returns {Array} Recent log entries
   */
  getRecentActivity(count = 50) {
    const logs = this.getLogs();
    return logs.slice(-count);
  }
};

// Make available globally
if (typeof window !== 'undefined') {
  window.ActivityLogger = ActivityLogger;
}
