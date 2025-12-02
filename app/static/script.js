const API_BASE_URL = typeof CONFIG !== 'undefined' ? CONFIG.API_BASE_URL : '';
const AUTH_ENDPOINTS = typeof CONFIG !== 'undefined' ? CONFIG.AUTH_ENDPOINTS : { login: '/auth/login', status: '/auth/status' };
const APPLY_ENDPOINTS = typeof CONFIG !== 'undefined' ? CONFIG.APPLY_ENDPOINTS : { bulk: '/apply/bulk' };
const HH_ENDPOINTS = typeof CONFIG !== 'undefined' ? CONFIG.HH_ENDPOINTS : { profile: '/hh/profile', resumes: '/hh/resumes' };
const SCHEDULER_ENDPOINTS = typeof CONFIG !== 'undefined' ? CONFIG.SCHEDULER_ENDPOINTS : {
    status: '/scheduler/status',
    settings: '/scheduler/settings',
    enable: '/scheduler/enable',
    disable: '/scheduler/disable',
    run: '/scheduler/run',
    history: '/scheduler/history'
};
const HH_DAILY_LIMIT = typeof CONFIG !== 'undefined' ? CONFIG.HH_LIMITS.DAILY_LIMIT : 200;
const HH_WARNING_THRESHOLD = typeof CONFIG !== 'undefined' ? CONFIG.HH_LIMITS.WARNING_THRESHOLD : 150;
const HH_MAX_PER_REQUEST = typeof CONFIG !== 'undefined' ? CONFIG.HH_LIMITS.MAX_PER_REQUEST : 50;

function getTodayKey() {
    const today = new Date();
    return `applybot_daily_${today.getFullYear()}-${today.getMonth() + 1}-${today.getDate()}`;
}

function getDailyCount() {
    const key = getTodayKey();
    const stored = localStorage.getItem(key);
    return stored ? parseInt(stored, 10) : 0;
}

function incrementDailyCount(count) {
    const key = getTodayKey();
    const current = getDailyCount();
    const newCount = current + count;
    localStorage.setItem(key, newCount.toString());
    
    // Clean up old keys (older than 7 days)
    cleanupOldKeys();
    
    return newCount;
}

function cleanupOldKeys() {
    const today = new Date();
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('applybot_daily_') && key !== getTodayKey()) {
            const datePart = key.replace('applybot_daily_', '');
            const keyDate = new Date(datePart);
            const diffDays = (today - keyDate) / (1000 * 60 * 60 * 24);
            if (diffDays > 7) {
                localStorage.removeItem(key);
            }
        }
    }
}

function playCompletionSound() {
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.frequency.value = 800;
        oscillator.type = 'sine';
        gainNode.gain.value = 0.3;
        
        oscillator.start();
        setTimeout(() => {
            oscillator.stop();
            audioContext.close();
        }, 200);
    } catch (e) {
        // Audio not available
    }
}

function showCompletionAlert(successCount, totalCount) {
    const safeSuccessCount = parseInt(successCount, 10) || 0;
    const safeTotalCount = parseInt(totalCount, 10) || 0;

    if (Notification.permission === 'granted') {
        new Notification('ApplyBot - Завершено!', {
            body: `Отправлено ${safeSuccessCount} из ${safeTotalCount} откликов`,
            icon: '📋'
        });
    } else if (Notification.permission !== 'denied') {
        Notification.requestPermission();
    }

    playCompletionSound();

    let originalTitle = document.title;
    let flashCount = 0;
    const flashInterval = setInterval(() => {
        document.title = flashCount % 2 === 0 ? `✅ Готово! (${safeSuccessCount})` : originalTitle;
        flashCount++;
        if (flashCount > 6) {
            clearInterval(flashInterval);
            document.title = originalTitle;
        }
    }, 500);
}

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

document.addEventListener('DOMContentLoaded', () => {
    const loginBtn = document.getElementById('login-btn');
    const authStatus = document.getElementById('auth-status');
    const authStatusText = document.getElementById('auth-status-text');
    const position = document.getElementById('position');
    const resume = document.getElementById('resume');
    const skills = document.getElementById('skills');
    const experience = document.getElementById('experience');
    const resumeId = document.getElementById('resume-id');
    const resumeSelect = document.getElementById('resume-select');
    const excludeCompanies = document.getElementById('exclude-companies');
    const salaryMin = document.getElementById('salary-min');
    const remoteOnly = document.getElementById('remote-only');
    const useAiAssistant = document.getElementById('use-ai-assistant');
    const experienceLevel = document.getElementById('experience-level');
    const maxApplications = document.getElementById('max-applications');
    const applyBtn = document.getElementById('apply-btn');
    const loadProfileBtn = document.getElementById('load-profile-btn');
    const applyResults = document.getElementById('apply-results');
    const applyResultsList = document.getElementById('apply-results-list');
    const progressSection = document.getElementById('progress-section');
    const progressText = document.getElementById('progress-text');
    const progressBar = document.getElementById('progress-bar');
    const progressEta = document.getElementById('progress-eta');
    const dailyCountEl = document.getElementById('daily-count');
    const dailyCounter = document.getElementById('daily-counter');

    updateDailyCounterDisplay();
    
    function updateDailyCounterDisplay() {
        const count = getDailyCount();
        dailyCountEl.textContent = count;
        
        // Update color based on count
        if (count >= HH_DAILY_LIMIT) {
            dailyCountEl.style.color = '#f44336';
            dailyCounter.style.background = '#ffebee';
            applyBtn.disabled = true;
            applyBtn.textContent = '🚫 Дневной лимит достигнут';
            applyBtn.style.background = '#ccc';
        } else if (count >= HH_WARNING_THRESHOLD) {
            dailyCountEl.style.color = '#ff9800';
            dailyCounter.style.background = '#fff3e0';
        } else {
            dailyCountEl.style.color = '#4CAF50';
            dailyCounter.style.background = '#f5f5f5';
        }
    }
    
    function isDailyLimitReached() {
        return getDailyCount() >= HH_DAILY_LIMIT;
    }

    // Event Listeners
    loginBtn.addEventListener('click', handleLogin);
    applyBtn.addEventListener('click', handleBulkApply);
    loadProfileBtn.addEventListener('click', loadProfileFromHH);
    resumeSelect.addEventListener('change', handleResumeSelect);
    checkAuthStatus();

    function handleLogin() {
        window.location.href = API_BASE_URL + AUTH_ENDPOINTS.login;
    }

    function handleResumeSelect() {
        const selectedValue = resumeSelect.value;
        resumeId.value = selectedValue;
        
        if (selectedValue) {
            loadUserProfileFromHH(selectedValue).then(profile => {
                populateFormFields(profile);
                showNotification('Profile loaded with selected resume!', 'success');
            }).catch(() => {});
        }
    }

    async function loadResumes() {
        try {
            const response = await fetch(API_BASE_URL + HH_ENDPOINTS.resumes, {
                method: 'GET',
                credentials: 'include'
            });

            if (!response.ok) {
                throw new Error('Failed to load resumes');
            }

            const resumes = await response.json();
            
            // Clear existing options
            resumeSelect.innerHTML = '';

            if (resumes.length === 0) {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = '-- No resumes found --';
                resumeSelect.appendChild(option);
                resumeSelect.disabled = true;
                return;
            }

            const placeholder = document.createElement('option');
            placeholder.value = '';
            placeholder.textContent = '-- Select a resume --';
            resumeSelect.appendChild(placeholder);

            resumes.forEach(r => {
                const option = document.createElement('option');
                option.value = r.id;
                option.textContent = `${r.title} (${r.status})`;
                resumeSelect.appendChild(option);
            });

            resumeSelect.disabled = false;

            if (resumes.length === 1) {
                resumeSelect.value = resumes[0].id;
                resumeId.value = resumes[0].id;
            }
            
            return resumes;
        } catch (error) {
            resumeSelect.innerHTML = '<option value="">-- Error loading resumes --</option>';
            resumeSelect.disabled = true;
            return [];
        }
    }

    async function checkAuthStatus() {
        try {
            const response = await fetch(API_BASE_URL + AUTH_ENDPOINTS.status, {
                method: 'GET',
                credentials: 'include'
            });

            if (response.ok) {
                const data = await response.json();
                authStatus.classList.remove('hidden');

                if (data.authenticated) {
                    const userName = data.first_name 
                        ? `${data.first_name} ${data.last_name || ''}`.trim()
                        : (data.email || 'User');
                    authStatusText.textContent = `Authenticated as ${userName}`;
                    authStatusText.style.color = '#4CAF50';
                    loginBtn.textContent = 'Re-login with HeadHunter';
                    loginBtn.classList.remove('primary');
                    loginBtn.classList.add('secondary');

                    loadResumes().then(resumes => {
                        if (resumes && resumes.length > 0) {
                            const selectedResumeId = resumeSelect.value || resumes[0].id;
                            if (selectedResumeId) {
                                resumeId.value = selectedResumeId;
                                loadUserProfileFromHH(selectedResumeId).then(profile => {
                                    populateFormFields(profile);
                                }).catch(() => {});
                            }
                        }
                    });
                } else {
                    authStatusText.textContent = 'Not authenticated';
                    authStatusText.style.color = '#f44336';
                }
            }
        } catch (error) {
            authStatus.classList.remove('hidden');
            authStatusText.textContent = 'Not authenticated';
            authStatusText.style.color = '#f44336';
        }
    }

    async function loadUserProfileFromHH(selectedResumeId = null) {
        let url = API_BASE_URL + HH_ENDPOINTS.profile;
        if (selectedResumeId) {
            url += `?resume_id=${encodeURIComponent(selectedResumeId)}`;
        }
        
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            credentials: 'include'
        });

        if (!response.ok) {
            if (response.status === 401) {
                throw new Error('Please authenticate with HH.ru first. Click "Login with HeadHunter"');
            }
            throw new Error('Failed to load profile from HH.ru');
        }

        const profile = await response.json();
        localStorage.setItem('hhProfile', JSON.stringify(profile));
        return profile;
    }

    async function loadProfileFromHH(event) {
        const btn = event.target;
        const originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Loading...';

        try {
            // Use selected resume if available
            const selectedResumeId = resumeSelect.value || null;
            const profile = await loadUserProfileFromHH(selectedResumeId);
            populateFormFields(profile);
            showNotification('Profile loaded successfully from HH.ru!', 'success');
        } catch (error) {
            const safeMessage = error.message && error.message.includes('authenticate')
                ? 'Please authenticate with HH.ru first. Click "Login with HeadHunter"'
                : 'Failed to load profile. Please try again.';
            showNotification(safeMessage, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = originalText;
        }
    }

    function populateFormFields(profile) {
        if (position && profile.resume?.title) {
            position.value = profile.resume.title;
        }

        if (skills && profile.skills?.length > 0) {
            skills.value = profile.skills.join(', ');
        }

        if (experience && profile.experience?.length > 0) {
            const experienceText = profile.experience.map(exp => {
                const endDate = exp.end || 'Present';
                let text = `${exp.position} at ${exp.company} (${exp.start} - ${endDate})`;
                if (exp.description) {
                    text += `\n${exp.description}`;
                }
                return text;
            }).join('\n\n');
            experience.value = experienceText;
        }

        if (resumeId && profile.resume?.id) {
            resumeId.value = profile.resume.id;
        }

        if (resume) {
            let resumeText = '';

            if (profile.resume?.title) {
                resumeText += `Position: ${profile.resume.title}\n\n`;
            }

            if (profile.skills?.length > 0) {
                resumeText += `Skills: ${profile.skills.join(', ')}\n\n`;
            }

            if (profile.education?.level) {
                resumeText += `Education: ${profile.education.level}\n`;
                if (profile.education.primary?.length > 0) {
                    profile.education.primary.forEach(edu => {
                        resumeText += `- ${edu.organization || edu.name} (${edu.year || 'N/A'})\n`;
                    });
                }
                resumeText += '\n';
            }

            if (profile.languages?.length > 0) {
                resumeText += `Languages: ${profile.languages.map(l => `${l.name} (${l.level})`).join(', ')}\n`;
            }

            resume.value = resumeText.trim();
        }
    }

    function showNotification(message, type = 'info') {
        const existingNotifications = document.querySelectorAll('.notification');
        existingNotifications.forEach(n => n.remove());

        // Validate type against allowlist to prevent CSS class injection
        const validTypes = ['success', 'error', 'warning', 'info'];
        const safeType = validTypes.includes(type) ? type : 'info';

        const notification = document.createElement('div');
        notification.className = `notification notification-${safeType}`;
        notification.textContent = String(message);

        const bgColors = {
            success: '#4CAF50',
            error: '#f44336',
            warning: '#ff9800',
            info: '#2196F3'
        };

        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            background: ${bgColors[safeType]};
            color: white;
            border-radius: 4px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 10000;
            max-width: 400px;
            animation: slideIn 0.3s ease-out;
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }

    async function handleBulkApply() {
        try {
            const requestData = {
                position: position.value.trim(),
                resume: resume.value.trim(),
                skills: skills.value.trim(),
                experience: experience.value.trim(),
                resume_id: resumeId.value.trim()
            };

            for (const [key, value] of Object.entries(requestData)) {
                if (!value) {
                    alert(`Please fill in the ${key.replace('_', ' ')} field`);
                    return;
                }
            }

            if (excludeCompanies.value.trim()) {
                requestData.exclude_companies = excludeCompanies.value.split(',').map(c => c.trim());
            }

            if (salaryMin.value.trim()) {
                requestData.salary_min = parseInt(salaryMin.value);
            }

            requestData.remote_only = remoteOnly.checked;
            requestData.use_cover_letter = useAiAssistant.checked;

            if (experienceLevel.value) {
                requestData.experience_level = experienceLevel.value;
            }

            let max = parseInt(maxApplications.value) || 10;
            if (max < 1) max = 1;
            if (max > HH_MAX_PER_REQUEST) max = HH_MAX_PER_REQUEST;
            maxApplications.value = max;

            if (isDailyLimitReached()) {
                showNotification('🚫 Дневной лимит HH.ru (200 откликов) достигнут. Попробуйте завтра.', 'error');
                return;
            }

            const currentDailyCount = getDailyCount();
            const remaining = HH_DAILY_LIMIT - currentDailyCount;
            if (max > remaining) {
                max = remaining;
                maxApplications.value = max;
                showNotification(`Ограничено до ${max} откликов (дневной лимит)`, 'warning');
            }

            const timingConfig = typeof CONFIG !== 'undefined' ? CONFIG.TIMING : { WITH_COVER_LETTER: 15, WITHOUT_COVER_LETTER: 2 };
            const timePerApp = useAiAssistant.checked ? timingConfig.WITH_COVER_LETTER : timingConfig.WITHOUT_COVER_LETTER;
            const estimatedTime = max * timePerApp;
            const estimatedMinutes = Math.ceil(estimatedTime / 60);

            applyBtn.textContent = 'Applying...';
            applyBtn.disabled = true;

            progressSection.classList.remove('hidden');
            progressBar.style.width = '0%';
            progressText.textContent = `Starting bulk application (0/${max})...`;
            progressEta.textContent = `Estimated time: ~${estimatedMinutes} min`;

            let progressInterval = null;
            let currentProgress = 0;
            progressInterval = setInterval(() => {
                if (currentProgress < 95) {
                    currentProgress += (100 / max) * 0.5; // Slow progress simulation
                    progressBar.style.width = Math.min(currentProgress, 95) + '%';
                    const estimated = Math.floor(currentProgress / (100 / max));
                    progressText.textContent = `Processing applications (~${estimated}/${max})...`;
                }
            }, timePerApp * 500);

            const url = `${API_BASE_URL}${APPLY_ENDPOINTS.bulk}?max_applications=${max}`;

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 600000);

            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(requestData),
                    signal: controller.signal
                });

                clearTimeout(timeoutId);
                clearInterval(progressInterval);

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || `Bulk application failed: ${response.status}`);
                }

                const data = await response.json();

                progressBar.style.width = '100%';
                const results = Array.isArray(data) ? data : [];
                const successCount = parseInt(results.filter(r => r && r.status === 'success').length, 10) || 0;
                const totalCount = parseInt(results.length, 10) || 0;
                progressText.textContent = `Completed! ${successCount}/${totalCount} applications sent successfully.`;
                progressEta.textContent = '';

                if (successCount > 0) {
                    incrementDailyCount(successCount);
                    updateDailyCounterDisplay();
                }

                displayApplyResults(results);
                showNotification(`Successfully sent ${successCount} applications!`, 'success');
                showCompletionAlert(successCount, totalCount);

            } catch (fetchError) {
                clearInterval(progressInterval);
                if (fetchError.name === 'AbortError') {
                    progressText.textContent = 'Request timed out. Applications may still be processing on the server.';
                    progressEta.textContent = 'Check your HH.ru account for results.';
                    showNotification('Request timed out but applications may have been sent. Check HH.ru.', 'warning');
                } else {
                    throw fetchError;
                }
            }

        } catch (error) {
            progressSection.classList.add('hidden');
            showNotification('Bulk application failed. Please try again.', 'error');
        } finally {
            if (!isDailyLimitReached()) {
                applyBtn.textContent = 'Apply to Multiple Jobs';
                applyBtn.disabled = false;
                applyBtn.style.background = '';
            }
            updateDailyCounterDisplay();
        }
    }

    function displayApplyResults(results) {
        applyResultsList.innerHTML = '';

        if (!results || results.length === 0) {
            const noResults = document.createElement('p');
            noResults.textContent = 'No application results';
            applyResultsList.appendChild(noResults);
            applyResults.classList.remove('hidden');
            return;
        }

        // Allowlist of valid status values for CSS classes
        const validStatuses = ['success', 'error', 'pending', 'failed', 'skipped'];

        results.forEach(result => {
            const resultItem = document.createElement('div');
            // Validate status against allowlist to prevent CSS class injection
            const safeStatus = validStatuses.includes(result.status) ? result.status : '';
            resultItem.className = `result-item ${safeStatus}`;

            const title = document.createElement('h4');
            title.textContent = `${result.vacancy_title || 'Vacancy'} (ID: ${result.vacancy_id})`;
            resultItem.appendChild(title);

            const statusP = document.createElement('p');
            const statusStrong = document.createElement('strong');
            statusStrong.textContent = 'Status: ';
            statusP.appendChild(statusStrong);
            statusP.appendChild(document.createTextNode(result.status || 'Unknown'));
            resultItem.appendChild(statusP);

            if (result.error_detail) {
                const errorP = document.createElement('p');
                const errorStrong = document.createElement('strong');
                errorStrong.textContent = 'Error: ';
                errorP.appendChild(errorStrong);
                errorP.appendChild(document.createTextNode(result.error_detail));
                resultItem.appendChild(errorP);
            }

            if (result.cover_letter) {
                const details = document.createElement('details');
                const summary = document.createElement('summary');
                summary.textContent = 'Cover Letter';
                details.appendChild(summary);

                const coverLetterDiv = document.createElement('div');
                coverLetterDiv.className = 'cover-letter';
                const lines = String(result.cover_letter).split('\n');
                lines.forEach((line, index) => {
                    coverLetterDiv.appendChild(document.createTextNode(line));
                    if (index < lines.length - 1) {
                        coverLetterDiv.appendChild(document.createElement('br'));
                    }
                });
                details.appendChild(coverLetterDiv);
                resultItem.appendChild(details);
            }

            applyResultsList.appendChild(resultItem);
        });

        applyResults.classList.remove('hidden');
        applyResults.scrollIntoView({ behavior: 'smooth' });
    }

    // ==================== SCHEDULER FUNCTIONALITY ====================
    
    const schedulerEnabled = document.getElementById('scheduler-enabled');
    const schedulerStatusText = document.getElementById('scheduler-status-text');
    const nextRunInfo = document.getElementById('next-run-info');
    const scheduleHour = document.getElementById('schedule-hour');
    const scheduleMinute = document.getElementById('schedule-minute');
    const scheduleTimezone = document.getElementById('schedule-timezone');
    const scheduleMaxApplications = document.getElementById('schedule-max-applications');
    const scheduleUseFormParams = document.getElementById('schedule-use-form-params');
    const saveSchedulerBtn = document.getElementById('save-scheduler-btn');
    const runNowBtn = document.getElementById('run-now-btn');
    const stopJobBtn = document.getElementById('stop-job-btn');
    const lastRunTime = document.getElementById('last-run-time');
    const lastRunResult = document.getElementById('last-run-result');
    const lastRunCount = document.getElementById('last-run-count');
    const totalApplications = document.getElementById('total-applications');
    const schedulerHistoryList = document.getElementById('scheduler-history-list');

    // Auto-polling for scheduler status
    let schedulerPollingInterval = null;
    
    function startSchedulerPolling() {
        if (schedulerPollingInterval) return;
        schedulerPollingInterval = setInterval(() => {
            loadSchedulerStatus();
            loadSchedulerHistory();
        }, 5000); // Poll every 5 seconds
    }
    
    function stopSchedulerPolling() {
        if (schedulerPollingInterval) {
            clearInterval(schedulerPollingInterval);
            schedulerPollingInterval = null;
        }
    }

    // Initialize scheduler UI
    if (schedulerEnabled) {
        loadSchedulerStatus();
        loadSchedulerHistory();

        schedulerEnabled.addEventListener('change', handleSchedulerToggle);
        saveSchedulerBtn.addEventListener('click', saveSchedulerSettings);
        runNowBtn.addEventListener('click', triggerManualRun);
        stopJobBtn.addEventListener('click', stopRunningJob);
    }

    async function loadSchedulerStatus() {
        try {
            const response = await fetch(API_BASE_URL + SCHEDULER_ENDPOINTS.status, {
                method: 'GET',
                credentials: 'include'
            });

            if (!response.ok) {
                throw new Error('Failed to load scheduler status');
            }

            const data = await response.json();
            updateSchedulerUI(data);
        } catch (error) {
            schedulerStatusText.textContent = 'Ошибка загрузки';
            schedulerStatusText.style.color = '#f44336';
        }
    }

    function updateSchedulerUI(data) {
        const isRunning = data.scheduler_running;
        const userSettings = data.user_settings;

        if (isRunning) {
            schedulerStatusText.textContent = userSettings?.enabled ? '✅ Активен' : '⏸️ Остановлен';
            schedulerStatusText.style.color = userSettings?.enabled ? '#4CAF50' : '#ff9800';
        } else {
            schedulerStatusText.textContent = '❌ Не запущен';
            schedulerStatusText.style.color = '#f44336';
        }

        if (data.next_scheduled_run) {
            const nextRun = new Date(data.next_scheduled_run);
            nextRunInfo.textContent = `Следующий запуск: ${nextRun.toLocaleString('ru-RU')}`;
        } else {
            nextRunInfo.textContent = '';
        }

        if (userSettings) {
            schedulerEnabled.checked = userSettings.enabled;
            
            if (userSettings.schedule) {
                scheduleHour.value = userSettings.schedule.hour;
                scheduleMinute.value = userSettings.schedule.minute;
                scheduleTimezone.value = userSettings.schedule.timezone;
                
                // Set days checkboxes
                const days = userSettings.schedule.days.split(',');
                document.querySelectorAll('input[name="schedule-day"]').forEach(cb => {
                    cb.checked = days.includes(cb.value);
                });
            }

            scheduleMaxApplications.value = userSettings.max_applications_per_run;

            // Statistics
            if (userSettings.last_run_at) {
                const lastRun = new Date(userSettings.last_run_at);
                lastRunTime.textContent = lastRun.toLocaleString('ru-RU');
            }
            
            const validStatuses = ['completed', 'failed', 'running'];
            const safeStatus = validStatuses.includes(userSettings.last_run_status) 
                ? userSettings.last_run_status 
                : '—';
            lastRunResult.textContent = safeStatus;
            lastRunCount.textContent = userSettings.last_run_applications || 0;
            totalApplications.textContent = userSettings.total_applications || 0;

            if (userSettings.next_run_at) {
                const nextRun = new Date(userSettings.next_run_at);
                nextRunInfo.textContent = `Следующий запуск: ${nextRun.toLocaleString('ru-RU')}`;
            }
        }
    }

    async function handleSchedulerToggle() {
        // Save settings with the new enabled state
        // This ensures settings exist before enabling
        const success = await saveSchedulerSettings();
        if (!success) {
            schedulerEnabled.checked = !schedulerEnabled.checked;
        }
    }

    async function saveSchedulerSettings() {
        const days = Array.from(document.querySelectorAll('input[name="schedule-day"]:checked'))
            .map(cb => cb.value)
            .join(',');

        if (!days) {
            showNotification('Выберите хотя бы один день недели', 'error');
            return false;
        }

        // Build search criteria from form or use current form values
        let searchCriteria = null;
        if (scheduleUseFormParams.checked) {
            const positionVal = position.value.trim();
            const resumeIdVal = resumeId.value.trim();

            if (!positionVal || !resumeIdVal) {
                showNotification('Заполните поля "Position" и выберите резюме в форме выше', 'error');
                return false;
            }

            searchCriteria = {
                position: positionVal,
                resume_id: resumeIdVal,
                skills: skills.value.trim() || null,
                experience: experience.value.trim() || null,
                exclude_companies: excludeCompanies.value.trim() 
                    ? excludeCompanies.value.split(',').map(c => c.trim())
                    : null,
                salary_min: salaryMin.value.trim() ? parseInt(salaryMin.value) : null,
                remote_only: remoteOnly.checked,
                experience_level: experienceLevel.value || null,
                use_cover_letter: useAiAssistant.checked
            };
        }

        const requestData = {
            enabled: schedulerEnabled.checked,
            schedule: {
                hour: parseInt(scheduleHour.value) || 9,
                minute: parseInt(scheduleMinute.value) || 0,
                days: days,
                timezone: scheduleTimezone.value || 'Europe/Moscow'
            },
            max_applications_per_run: parseInt(scheduleMaxApplications.value) || 10,
            search_criteria: searchCriteria
        };

        saveSchedulerBtn.disabled = true;
        saveSchedulerBtn.textContent = 'Сохранение...';

        try {
            const response = await fetch(API_BASE_URL + SCHEDULER_ENDPOINTS.settings, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData),
                credentials: 'include'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to save settings');
            }

            const statusMsg = schedulerEnabled.checked 
                ? '✅ Планировщик включен' 
                : '⏸️ Планировщик отключен';
            showNotification(statusMsg, 'success');
            loadSchedulerStatus();
            return true;
        } catch (error) {
            showNotification('Ошибка сохранения настроек', 'error');
            return false;
        } finally {
            saveSchedulerBtn.disabled = false;
            saveSchedulerBtn.textContent = '💾 Сохранить настройки';
        }
    }

    async function triggerManualRun() {
        const maxApps = parseInt(scheduleMaxApplications.value) || 10;

        runNowBtn.disabled = true;
        runNowBtn.textContent = 'Запуск...';

        try {
            const response = await fetch(API_BASE_URL + SCHEDULER_ENDPOINTS.run, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ max_applications: maxApps }),
                credentials: 'include'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to trigger run');
            }

            const result = await response.json();
            // Use static message for security - API message is only for logging
            showNotification('Запуск начат', 'success');

            // Refresh status after a delay
            setTimeout(() => {
                loadSchedulerStatus();
                loadSchedulerHistory();
            }, 2000);
        } catch (error) {
            showNotification('Ошибка запуска', 'error');
        } finally {
            runNowBtn.disabled = false;
            runNowBtn.textContent = '▶️ Запустить сейчас';
        }
    }

    async function stopRunningJob() {
        stopJobBtn.disabled = true;
        stopJobBtn.textContent = 'Останавливаем...';

        try {
            const response = await fetch(API_BASE_URL + SCHEDULER_ENDPOINTS.stop, {
                method: 'POST',
                credentials: 'include'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to stop job');
            }

            showNotification('⏹️ Остановка запрошена', 'success');

            // Refresh status after a delay
            setTimeout(() => {
                loadSchedulerStatus();
                loadSchedulerHistory();
            }, 2000);
        } catch (error) {
            showNotification('Ошибка остановки', 'error');
        } finally {
            stopJobBtn.disabled = false;
            stopJobBtn.textContent = '⏹️ Остановить';
        }
    }

    async function loadSchedulerHistory() {
        try {
            const response = await fetch(API_BASE_URL + SCHEDULER_ENDPOINTS.history + '?limit=10', {
                method: 'GET',
                credentials: 'include'
            });

            if (!response.ok) {
                throw new Error('Failed to load history');
            }

            const data = await response.json();
            displaySchedulerHistory(data.runs || []);
        } catch (error) {
            schedulerHistoryList.innerHTML = '<p style="color: #666;">Не удалось загрузить историю</p>';
        }
    }

    function displaySchedulerHistory(runs) {
        schedulerHistoryList.innerHTML = '';

        if (!runs || runs.length === 0) {
            const noHistory = document.createElement('p');
            noHistory.style.color = '#666';
            noHistory.textContent = 'История запусков пуста';
            schedulerHistoryList.appendChild(noHistory);
            stopSchedulerPolling();
            stopJobBtn.style.display = 'none';
            runNowBtn.style.display = 'inline-block';
            return;
        }

        // Check if there's a running job and start/stop polling
        const hasRunningJob = runs.some(run => run.status === 'running');
        if (hasRunningJob) {
            startSchedulerPolling();
            stopJobBtn.style.display = 'inline-block';
            runNowBtn.style.display = 'none';
        } else {
            stopSchedulerPolling();
            stopJobBtn.style.display = 'none';
            runNowBtn.style.display = 'inline-block';
        }

        const validStatuses = ['completed', 'failed', 'running'];

        runs.forEach(run => {
            const runItem = document.createElement('div');
            const safeStatus = validStatuses.includes(run.status) ? run.status : 'unknown';
            runItem.className = `result-item ${safeStatus === 'completed' ? 'success' : safeStatus === 'failed' ? 'error' : ''}`;

            const startedAt = new Date(run.started_at);
            const finishedAt = run.finished_at ? new Date(run.finished_at) : null;

            const header = document.createElement('h4');
            header.textContent = `Запуск ${startedAt.toLocaleString('ru-RU')}`;
            runItem.appendChild(header);

            const statusP = document.createElement('p');
            statusP.innerHTML = `<strong>Статус:</strong> ${escapeHtml(safeStatus)}`;
            runItem.appendChild(statusP);

            const statsP = document.createElement('p');
            statsP.textContent = `Отправлено: ${run.applications_sent || 0} | Пропущено: ${run.applications_skipped || 0} | Ошибок: ${run.applications_failed || 0}`;
            runItem.appendChild(statsP);

            if (finishedAt) {
                const durationMs = finishedAt - startedAt;
                const durationMin = Math.round(durationMs / 60000);
                const durationP = document.createElement('p');
                durationP.style.color = '#666';
                durationP.style.fontSize = '0.9em';
                durationP.textContent = `Длительность: ${durationMin} мин`;
                runItem.appendChild(durationP);
            }

            if (run.error_message) {
                const errorP = document.createElement('p');
                errorP.style.color = '#f44336';
                errorP.textContent = `Ошибка: ${run.error_message}`;
                runItem.appendChild(errorP);
            }

            schedulerHistoryList.appendChild(runItem);
        });
    }
});
