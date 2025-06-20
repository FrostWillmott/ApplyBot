// Constants
// Use relative URL for API requests
// This works regardless of whether we're running in Docker or not
const API_BASE_URL = '';
const AUTH_ENDPOINTS = {
    login: '/auth/login',
    callback: '/auth/callback'
};
const APPLY_ENDPOINTS = {
    single: '/apply/single',
    bulk: '/apply/bulk',
    search: '/apply/search',
    analytics: '/apply/analytics'
};

// DOM Elements
document.addEventListener('DOMContentLoaded', () => {
    // Auth elements
    const loginBtn = document.getElementById('login-btn');
    const authStatus = document.getElementById('auth-status');
    const authStatusText = document.getElementById('auth-status-text');

    // Search elements
    const searchText = document.getElementById('search-text');
    const searchPage = document.getElementById('search-page');
    const searchPerPage = document.getElementById('search-per-page');
    const searchBtn = document.getElementById('search-btn');
    const searchResults = document.getElementById('search-results');
    const resultsList = document.getElementById('results-list');
    const prevPageBtn = document.getElementById('prev-page');
    const nextPageBtn = document.getElementById('next-page');
    const pageInfo = document.getElementById('page-info');

    // Apply elements - Single
    const vacancyId = document.getElementById('vacancy-id');
    const position = document.getElementById('position');
    const resume = document.getElementById('resume');
    const skills = document.getElementById('skills');
    const experience = document.getElementById('experience');
    const resumeId = document.getElementById('resume-id');
    const applySingleBtn = document.getElementById('apply-single-btn');

    // Apply elements - Bulk
    const bulkPosition = document.getElementById('bulk-position');
    const bulkResume = document.getElementById('bulk-resume');
    const bulkSkills = document.getElementById('bulk-skills');
    const bulkExperience = document.getElementById('bulk-experience');
    const bulkResumeId = document.getElementById('bulk-resume-id');
    const excludeCompanies = document.getElementById('exclude-companies');
    const salaryMin = document.getElementById('salary-min');
    const remoteOnly = document.getElementById('remote-only');
    const experienceLevel = document.getElementById('experience-level');
    const maxApplications = document.getElementById('max-applications');
    const applyBulkBtn = document.getElementById('apply-bulk-btn');

    // Apply results
    const applyResults = document.getElementById('apply-results');
    const applyResultsList = document.getElementById('apply-results-list');

    // Analytics elements
    const userId = document.getElementById('user-id');
    const days = document.getElementById('days');
    const analyticsBtn = document.getElementById('analytics-btn');
    const analyticsResults = document.getElementById('analytics-results');
    const analyticsData = document.getElementById('analytics-data');

    // Tab switching
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.getAttribute('data-tab');

            // Update active tab button
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Show active tab content
            tabContents.forEach(content => {
                content.classList.remove('active');
                if (content.id === `${tabName}-tab`) {
                    content.classList.add('active');
                }
            });
        });
    });

    // Event Listeners
    loginBtn.addEventListener('click', handleLogin);
    searchBtn.addEventListener('click', handleSearch);
    prevPageBtn.addEventListener('click', () => handlePageChange(-1));
    nextPageBtn.addEventListener('click', () => handlePageChange(1));
    applySingleBtn.addEventListener('click', handleSingleApply);
    applyBulkBtn.addEventListener('click', handleBulkApply);
    analyticsBtn.addEventListener('click', handleAnalytics);

    // Check if we're returning from auth callback
    checkAuthCallback();

    // Functions
    function handleLogin() {
        window.location.href = API_BASE_URL + AUTH_ENDPOINTS.login;
    }

    function checkAuthCallback() {
        // Check if URL contains code and state parameters
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');
        const state = urlParams.get('state');

        if (code && state) {
            // We're in the callback, show auth status
            authStatus.classList.remove('hidden');
            authStatusText.textContent = 'Authenticating...';

            // Clear URL parameters without reloading page
            window.history.replaceState({}, document.title, window.location.pathname);

            // Authentication was handled by the backend redirect
            authStatusText.textContent = 'Authenticated';
        }
    }

    async function handleSearch() {
        try {
            const query = searchText.value.trim();
            if (!query) {
                alert('Please enter a search query');
                return;
            }

            const page = parseInt(searchPage.value) || 0;
            const perPage = parseInt(searchPerPage.value) || 20;

            const url = `${API_BASE_URL}${APPLY_ENDPOINTS.search}?text=${encodeURIComponent(query)}&page=${page}&per_page=${perPage}`;

            // Show loading state
            searchBtn.textContent = 'Searching...';
            searchBtn.disabled = true;

            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`Search failed: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();
            displaySearchResults(data, page);

        } catch (error) {
            console.error('Search error:', error);
            alert(`Search failed: ${error.message}`);
        } finally {
            // Reset button state
            searchBtn.textContent = 'Search';
            searchBtn.disabled = false;
        }
    }

    function displaySearchResults(data, currentPage) {
        // Clear previous results
        resultsList.innerHTML = '';

        // Check if we have items
        if (!data.items || data.items.length === 0) {
            resultsList.innerHTML = '<p>No results found</p>';
            searchResults.classList.remove('hidden');
            return;
        }

        // Create result items
        data.items.forEach(item => {
            const resultItem = document.createElement('div');
            resultItem.className = 'result-item';

            // Format salary if available
            let salaryText = 'Salary not specified';
            if (item.salary) {
                salaryText = `${item.salary.from || ''} - ${item.salary.to || ''} ${item.salary.currency || ''}`;
            }

            resultItem.innerHTML = `
                <h4>${item.name}</h4>
                <p><strong>Company:</strong> ${item.employer?.name || 'Unknown'}</p>
                <p><strong>Salary:</strong> ${salaryText}</p>
                <p><strong>Location:</strong> ${item.area?.name || 'Not specified'}</p>
                <p><strong>ID:</strong> ${item.id}</p>
                <button class="btn small primary apply-from-search" data-id="${item.id}">Apply</button>
                <a href="${item.alternate_url}" target="_blank" class="btn small secondary">View on HH</a>
            `;

            resultsList.appendChild(resultItem);
        });

        // Add event listeners to apply buttons
        document.querySelectorAll('.apply-from-search').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.getAttribute('data-id');
                vacancyId.value = id;
                document.getElementById('apply-section').scrollIntoView({ behavior: 'smooth' });
            });
        });

        // Update pagination
        pageInfo.textContent = `Page ${currentPage + 1} of ${Math.ceil(data.found / data.per_page)}`;
        prevPageBtn.disabled = currentPage === 0;
        nextPageBtn.disabled = (currentPage + 1) * data.per_page >= data.found;

        // Show results section
        searchResults.classList.remove('hidden');
    }

    function handlePageChange(direction) {
        const currentPage = parseInt(searchPage.value) || 0;
        const newPage = currentPage + direction;

        if (newPage >= 0) {
            searchPage.value = newPage;
            handleSearch();
        }
    }

    async function handleSingleApply() {
        try {
            const id = vacancyId.value.trim();
            if (!id) {
                alert('Please enter a vacancy ID');
                return;
            }

            const requestData = {
                position: position.value.trim(),
                resume: resume.value.trim(),
                skills: skills.value.trim(),
                experience: experience.value.trim(),
                resume_id: resumeId.value.trim()
            };

            // Validate required fields
            for (const [key, value] of Object.entries(requestData)) {
                if (!value) {
                    alert(`Please fill in the ${key.replace('_', ' ')} field`);
                    return;
                }
            }

            // Show loading state
            applySingleBtn.textContent = 'Applying...';
            applySingleBtn.disabled = true;

            const url = `${API_BASE_URL}${APPLY_ENDPOINTS.single}/${id}`;
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `Application failed: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();
            displayApplyResults([data]);

        } catch (error) {
            console.error('Apply error:', error);
            alert(`Application failed: ${error.message}`);
        } finally {
            // Reset button state
            applySingleBtn.textContent = 'Apply';
            applySingleBtn.disabled = false;
        }
    }

    async function handleBulkApply() {
        try {
            const requestData = {
                position: bulkPosition.value.trim(),
                resume: bulkResume.value.trim(),
                skills: bulkSkills.value.trim(),
                experience: bulkExperience.value.trim(),
                resume_id: bulkResumeId.value.trim()
            };

            // Validate required fields
            for (const [key, value] of Object.entries(requestData)) {
                if (!value) {
                    alert(`Please fill in the ${key.replace('_', ' ')} field`);
                    return;
                }
            }

            // Add optional fields
            if (excludeCompanies.value.trim()) {
                requestData.exclude_companies = excludeCompanies.value.split(',').map(c => c.trim());
            }

            if (salaryMin.value.trim()) {
                requestData.salary_min = parseInt(salaryMin.value);
            }

            requestData.remote_only = remoteOnly.checked;

            if (experienceLevel.value) {
                requestData.experience_level = experienceLevel.value;
            }

            // Show loading state
            applyBulkBtn.textContent = 'Applying...';
            applyBulkBtn.disabled = true;

            const max = parseInt(maxApplications.value) || 20;
            const url = `${API_BASE_URL}${APPLY_ENDPOINTS.bulk}?max_applications=${max}`;

            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `Bulk application failed: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();
            displayApplyResults(data);

        } catch (error) {
            console.error('Bulk apply error:', error);
            alert(`Bulk application failed: ${error.message}`);
        } finally {
            // Reset button state
            applyBulkBtn.textContent = 'Apply to Multiple Jobs';
            applyBulkBtn.disabled = false;
        }
    }

    function displayApplyResults(results) {
        // Clear previous results
        applyResultsList.innerHTML = '';

        // Check if we have results
        if (!results || results.length === 0) {
            applyResultsList.innerHTML = '<p>No application results</p>';
            applyResults.classList.remove('hidden');
            return;
        }

        // Create result items
        results.forEach(result => {
            const resultItem = document.createElement('div');
            resultItem.className = `result-item ${result.status}`;

            let content = `
                <h4>${result.vacancy_title || 'Vacancy'} (ID: ${result.vacancy_id})</h4>
                <p><strong>Status:</strong> ${result.status}</p>
            `;

            if (result.error_detail) {
                content += `<p><strong>Error:</strong> ${result.error_detail}</p>`;
            }

            if (result.cover_letter) {
                content += `
                    <details>
                        <summary>Cover Letter</summary>
                        <div class="cover-letter">${result.cover_letter.replace(/\n/g, '<br>')}</div>
                    </details>
                `;
            }

            resultItem.innerHTML = content;
            applyResultsList.appendChild(resultItem);
        });

        // Show results section
        applyResults.classList.remove('hidden');
        applyResults.scrollIntoView({ behavior: 'smooth' });
    }

    async function handleAnalytics() {
        try {
            const id = userId.value.trim();
            if (!id) {
                alert('Please enter a user ID');
                return;
            }

            const daysValue = parseInt(days.value) || 30;

            // Show loading state
            analyticsBtn.textContent = 'Loading...';
            analyticsBtn.disabled = true;

            const url = `${API_BASE_URL}${APPLY_ENDPOINTS.analytics}/${id}?days=${daysValue}`;
            const response = await fetch(url);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `Analytics failed: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();
            displayAnalytics(data);

        } catch (error) {
            console.error('Analytics error:', error);
            alert(`Analytics failed: ${error.message}`);
        } finally {
            // Reset button state
            analyticsBtn.textContent = 'Get Analytics';
            analyticsBtn.disabled = false;
        }
    }

    function displayAnalytics(data) {
        // Clear previous results
        analyticsData.innerHTML = '';

        // Create analytics display
        const analyticsCard = document.createElement('div');
        analyticsCard.className = 'analytics-card';

        let content = `
            <h4>Application Statistics</h4>
            <p><strong>Total Applications:</strong> ${data.total_applications || 0}</p>
            <p><strong>Success Rate:</strong> ${data.success_rate || 0}%</p>
            <p><strong>Average Applications Per Day:</strong> ${data.avg_applications_per_day || 0}</p>
        `;

        if (data.applications_by_status) {
            content += '<h4>Applications by Status</h4><ul>';
            for (const [status, count] of Object.entries(data.applications_by_status)) {
                content += `<li>${status}: ${count}</li>`;
            }
            content += '</ul>';
        }

        analyticsCard.innerHTML = content;
        analyticsData.appendChild(analyticsCard);

        // Show results section
        analyticsResults.classList.remove('hidden');
    }
});
