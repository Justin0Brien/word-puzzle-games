/**
 * Game State Manager
 * Saves and restores game state to localStorage for seamless continuation
 */

const GameState = {
  PREFIX: 'wordPuzzleGames_state_',
  
  /**
   * Save game state to localStorage
   * @param {string} gameId - Unique identifier for the game (e.g., 'wordle', 'sudoku')
   * @param {Object} state - Game state object to save
   */
  save(gameId, state) {
    try {
      const key = this.PREFIX + gameId;
      const data = {
        ...state,
        savedAt: new Date().toISOString()
      };
      localStorage.setItem(key, JSON.stringify(data));
    } catch (e) {
      console.error('Error saving game state:', e);
    }
  },
  
  /**
   * Load game state from localStorage
   * @param {string} gameId - Unique identifier for the game
   * @returns {Object|null} - Saved state or null if none exists
   */
  load(gameId) {
    try {
      const key = this.PREFIX + gameId;
      const data = localStorage.getItem(key);
      if (!data) return null;
      return JSON.parse(data);
    } catch (e) {
      console.error('Error loading game state:', e);
      return null;
    }
  },
  
  /**
   * Clear saved game state
   * @param {string} gameId - Unique identifier for the game
   */
  clear(gameId) {
    try {
      const key = this.PREFIX + gameId;
      localStorage.removeItem(key);
    } catch (e) {
      console.error('Error clearing game state:', e);
    }
  },
  
  /**
   * Check if a saved game exists
   * @param {string} gameId - Unique identifier for the game
   * @returns {boolean}
   */
  exists(gameId) {
    const key = this.PREFIX + gameId;
    return localStorage.getItem(key) !== null;
  },
  
  /**
   * Get the age of a saved game in milliseconds
   * @param {string} gameId - Unique identifier for the game
   * @returns {number|null} - Age in ms or null if no save exists
   */
  getAge(gameId) {
    const state = this.load(gameId);
    if (!state || !state.savedAt) return null;
    return Date.now() - new Date(state.savedAt).getTime();
  },
  
  /**
   * Check if saved game is still valid (not too old)
   * @param {string} gameId - Unique identifier for the game
   * @param {number} maxAgeMs - Maximum age in milliseconds (default: 24 hours)
   * @returns {boolean}
   */
  isValid(gameId, maxAgeMs = 24 * 60 * 60 * 1000) {
    const age = this.getAge(gameId);
    if (age === null) return false;
    return age < maxAgeMs;
  }
};

// Make available globally
if (typeof window !== 'undefined') {
  window.GameState = GameState;
}
