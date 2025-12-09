const CONFIG = {
    API_BASE_URL: '',

    AUTH_ENDPOINTS: {
        login: '/auth/login',
        status: '/auth/status'
    },

    APPLY_ENDPOINTS: {
        bulk: '/apply/bulk',
        bulkStream: '/apply/bulk/stream'
    },

    HH_ENDPOINTS: {
        profile: '/hh/profile',
        resumes: '/hh/resumes'
    },

    SCHEDULER_ENDPOINTS: {
        status: '/scheduler/status',
        settings: '/scheduler/settings',
        enable: '/scheduler/enable',
        disable: '/scheduler/disable',
        run: '/scheduler/run',
        stop: '/scheduler/stop',
        history: '/scheduler/history'
    },

    HH_LIMITS: {
        MAX_PER_REQUEST: 50,
        DAILY_LIMIT: 200,
        WARNING_THRESHOLD: 150,
        MIN_COVER_LETTER_LENGTH: 50
    },

    TIMING: {
        WITH_COVER_LETTER: 6,
        WITHOUT_COVER_LETTER: 4,
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
    },

    SCHEDULER: {
        DEFAULT_HOUR: 9,
        DEFAULT_MINUTE: 0,
        DEFAULT_DAYS: 'mon,tue,wed,thu,fri',
        DEFAULT_TIMEZONE: 'Europe/Moscow',
        DEFAULT_MAX_APPLICATIONS: 10
    }
};

Object.freeze(CONFIG);
Object.freeze(CONFIG.AUTH_ENDPOINTS);
Object.freeze(CONFIG.APPLY_ENDPOINTS);
Object.freeze(CONFIG.HH_ENDPOINTS);
Object.freeze(CONFIG.SCHEDULER_ENDPOINTS);
Object.freeze(CONFIG.HH_LIMITS);
Object.freeze(CONFIG.TIMING);
Object.freeze(CONFIG.UI);
Object.freeze(CONFIG.STORAGE_KEYS);
Object.freeze(CONFIG.SCHEDULER);
