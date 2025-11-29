const CONFIG = {
    API_BASE_URL: '',

    AUTH_ENDPOINTS: {
        login: '/auth/login',
        status: '/auth/status'
    },

    APPLY_ENDPOINTS: {
        bulk: '/apply/bulk'
    },

    HH_ENDPOINTS: {
        profile: '/hh/profile',
        resumes: '/hh/resumes'
    },

    HH_LIMITS: {
        MAX_PER_REQUEST: 50,
        DAILY_LIMIT: 200,
        WARNING_THRESHOLD: 150,
        MIN_COVER_LETTER_LENGTH: 50
    },

    TIMING: {
        WITH_COVER_LETTER: 15,
        WITHOUT_COVER_LETTER: 2,
        REQUEST_TIMEOUT: 600000
    },

    UI: {
        DEFAULT_MAX_APPLICATIONS: 10,
        NOTIFICATION_DURATION: 5000,
        PROGRESS_UPDATE_MULTIPLIER: 500
    },

    STORAGE_KEYS: {
        DAILY_COUNT_PREFIX: 'applybot_daily_',
        PROFILE_CACHE: 'hhProfile'
    }
};

Object.freeze(CONFIG);
Object.freeze(CONFIG.AUTH_ENDPOINTS);
Object.freeze(CONFIG.APPLY_ENDPOINTS);
Object.freeze(CONFIG.HH_ENDPOINTS);
Object.freeze(CONFIG.HH_LIMITS);
Object.freeze(CONFIG.TIMING);
Object.freeze(CONFIG.UI);
Object.freeze(CONFIG.STORAGE_KEYS);

