(() => {
    const DISMISS_KEY = 'pwa_install_dismissed';
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches ||
        window.navigator.standalone === true;
    const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);

    if (isStandalone) {
        return;
    }

    let deferredPrompt = null;
    let bannerShown = false;

    function createBanner(message, showInstall) {
        if (localStorage.getItem(DISMISS_KEY) === '1' || bannerShown) {
            return;
        }

        const banner = document.createElement('div');
        banner.className = 'pwa-install-banner';
        banner.innerHTML = `
            <div class="pwa-install-banner__icon">
                <img src="/static/Cloudface-ai-logo.png" alt="CloudFace AI">
            </div>
            <div class="pwa-install-banner__text">${message}</div>
            <div class="pwa-install-banner__actions">
                ${showInstall ? '<button class="pwa-install-banner__btn">Install</button>' : ''}
                <button class="pwa-install-banner__btn pwa-install-banner__btn--secondary">Not now</button>
            </div>
        `;

        const actionButtons = banner.querySelectorAll('button');
        const installButton = showInstall ? actionButtons[0] : null;
        const dismissButton = showInstall ? actionButtons[1] : actionButtons[0];

        if (installButton) {
            installButton.addEventListener('click', async () => {
                banner.remove();
                if (!deferredPrompt) {
                    return;
                }
                deferredPrompt.prompt();
                try {
                    const choice = await deferredPrompt.userChoice;
                    if (choice.outcome !== 'accepted') {
                        localStorage.setItem(DISMISS_KEY, '1');
                    }
                } catch (error) {
                    localStorage.setItem(DISMISS_KEY, '1');
                } finally {
                    deferredPrompt = null;
                }
            });
        }

        dismissButton.addEventListener('click', () => {
            localStorage.setItem(DISMISS_KEY, '1');
            banner.remove();
        });

        document.body.appendChild(banner);
        bannerShown = true;
    }

    window.addEventListener('beforeinstallprompt', (event) => {
        event.preventDefault();
        deferredPrompt = event;
        createBanner('Install CloudFace AI for faster access and offline support.', true);
    });

    if (isIOS) {
        window.addEventListener('load', () => {
            createBanner('Install from Safari: tap Share → Add to Home Screen.', false);
        });
    } else {
        window.addEventListener('load', () => {
            setTimeout(() => {
                if (!deferredPrompt && !isStandalone && !bannerShown) {
                    createBanner('Install CloudFace AI from your browser menu (Install App).', false);
                }
            }, 5000);
        });
    }

    if ('serviceWorker' in navigator) {
        const isSecureContext = location.protocol === 'https:' ||
            location.hostname === 'localhost' ||
            location.hostname === '127.0.0.1';

        if (isSecureContext) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/sw.js').catch(() => {});
            });
        }
    }

    const pathName = window.location.pathname;
    const isBlogPage = pathName === '/blog' || pathName.startsWith('/blog/');

    function ensureSeoStyles() {
        if (!isBlogPage || document.getElementById('seo-enhancements-style')) {
            return;
        }

        const style = document.createElement('style');
        style.id = 'seo-enhancements-style';
        style.textContent = `
            .internal-links {
                margin: 2.5rem 0 1rem 0;
                padding: 1.5rem;
                border: 1px solid #dadce0;
                border-radius: 16px;
                background: #ffffff;
                box-shadow: 0 1px 3px rgba(0,0,0,0.12);
            }
            .internal-links h2 {
                margin: 0 0 1rem 0;
                font-size: 1.3rem;
                color: #202124;
            }
            .internal-links-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 12px;
            }
            .internal-link-card {
                display: block;
                padding: 12px 14px;
                border: 1px solid #e0e0e0;
                border-radius: 12px;
                text-decoration: none;
                background: #fafafa;
                color: #202124;
                transition: background 0.1s ease;
            }
            .internal-link-card:hover {
                background: #f1f3f4;
            }
            .internal-link-card strong {
                display: block;
                margin-bottom: 4px;
                color: #1a73e8;
            }
            .internal-link-card span {
                display: block;
                font-size: 0.9rem;
                color: #5f6368;
            }
        `;
        document.head.appendChild(style);
    }

    function addInternalLinksBlock() {
        if (!isBlogPage || document.querySelector('.internal-links')) {
            return;
        }

        const blogBodies = document.querySelectorAll('.blog-body');
        const blogArticle = document.querySelector('article.blog-content');
        const target = blogBodies.length ? blogBodies[blogBodies.length - 1] : blogArticle;

        if (!target) {
            return;
        }

        const block = document.createElement('section');
        block.className = 'internal-links';
        block.innerHTML = `
            <h2>Explore CloudFace AI</h2>
            <div class="internal-links-grid">
                <a class="internal-link-card" href="/app">
                    <strong>Try the App</strong>
                    <span>Run face search in minutes.</span>
                </a>
                <a class="internal-link-card" href="/image-tools">
                    <strong>Image Tools</strong>
                    <span>Batch watermark and resize.</span>
                </a>
                <a class="internal-link-card" href="/pricing">
                    <strong>Pricing Plans</strong>
                    <span>Choose the right plan.</span>
                </a>
                <a class="internal-link-card" href="/how-it-works">
                    <strong>How It Works</strong>
                    <span>See the full workflow.</span>
                </a>
                <a class="internal-link-card" href="/blog">
                    <strong>More Articles</strong>
                    <span>Read the latest guides.</span>
                </a>
            </div>
        `;

        target.insertAdjacentElement('afterend', block);
    }

    function enableLazyLoading() {
        if (!isBlogPage) {
            return;
        }

        const blogImages = document.querySelectorAll('.blog-body img, article.blog-content img, .blog-image img');
        blogImages.forEach((img) => {
            if (!img.getAttribute('loading')) {
                img.setAttribute('loading', 'lazy');
            }
            if (!img.getAttribute('decoding')) {
                img.setAttribute('decoding', 'async');
            }
        });
    }

    if (isBlogPage) {
        window.addEventListener('load', () => {
            ensureSeoStyles();
            addInternalLinksBlock();
            enableLazyLoading();
        });
    }

    function sendAnalytics(url, payload, useBeacon = false) {
        try {
            const body = JSON.stringify(payload || {});
            if (useBeacon && navigator.sendBeacon) {
                const blob = new Blob([body], { type: 'application/json' });
                navigator.sendBeacon(url, blob);
                return;
            }
            fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body
            }).catch(() => {});
        } catch (error) {
            // ignore
        }
    }

    function initAnalytics() {
        const pageUrl = window.location.pathname + window.location.search;
        const pageTitle = document.title || '';
        const pingIntervalMs = 30000;
        let lastPingAt = Date.now();

        sendAnalytics('/api/analytics/pageview', {
            page_url: pageUrl,
            page_title: pageTitle
        });

        setInterval(() => {
            const now = Date.now();
            const seconds = Math.round((now - lastPingAt) / 1000);
            lastPingAt = now;
            sendAnalytics('/api/analytics/ping', {
                page_url: pageUrl,
                seconds
            });
        }, pingIntervalMs);

        window.addEventListener('beforeunload', () => {
            const now = Date.now();
            const seconds = Math.round((now - lastPingAt) / 1000);
            sendAnalytics('/api/analytics/ping', {
                page_url: pageUrl,
                seconds
            }, true);
        });

        window.addEventListener('error', (event) => {
            sendAnalytics('/api/analytics/error', {
                page_url: pageUrl,
                message: event.message,
                source: event.filename,
                line: event.lineno,
                col: event.colno,
                stack: event.error && event.error.stack ? event.error.stack : ''
            });
        });

        window.addEventListener('unhandledrejection', (event) => {
            sendAnalytics('/api/analytics/error', {
                page_url: pageUrl,
                message: event.reason && event.reason.message ? event.reason.message : 'Unhandled rejection',
                stack: event.reason && event.reason.stack ? event.reason.stack : ''
            });
        });
    }

    function openUpgradeModal() {
        const modal = document.getElementById('upgradeModal');
        if (modal) {
            modal.style.display = 'flex';
        }
    }

    function closeUpgradeModal() {
        const modal = document.getElementById('upgradeModal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    function openProfileModal(profile) {
        const modal = document.getElementById('profileModal');
        if (!modal) return;
        const nameField = document.getElementById('profileName');
        const cityField = document.getElementById('profileCity');
        const phoneField = document.getElementById('profilePhone');
        const useCaseField = document.getElementById('profileUseCase');
        if (nameField && profile && profile.name) nameField.value = profile.name;
        if (cityField && profile && profile.city) cityField.value = profile.city;
        if (phoneField && profile && profile.phone) phoneField.value = profile.phone;
        if (useCaseField && profile && profile.use_case) useCaseField.value = profile.use_case;
        modal.style.display = 'flex';
    }

    function closeProfileModal() {
        const modal = document.getElementById('profileModal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    function openDiscountModal() {
        const modal = document.getElementById('discountModal');
        if (modal) {
            modal.style.display = 'flex';
        }
    }

    function closeDiscountModal() {
        const modal = document.getElementById('discountModal');
        if (modal) {
            modal.style.display = 'none';
        }
        try {
            localStorage.setItem('cf_discount_popup_dismissed', '1');
        } catch (e) {
            // ignore
        }
    }

    async function saveProfileDetails() {
        const nameField = document.getElementById('profileName');
        const cityField = document.getElementById('profileCity');
        const phoneField = document.getElementById('profilePhone');
        const useCaseField = document.getElementById('profileUseCase');
        const payload = {
            name: nameField ? nameField.value.trim() : '',
            city: cityField ? cityField.value.trim() : '',
            phone: phoneField ? phoneField.value.trim() : '',
            use_case: useCaseField ? useCaseField.value.trim() : ''
        };
        try {
            const response = await fetch('/api/user-profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            if (result.success) {
                closeProfileModal();
            }
        } catch (e) {
            // ignore
        }
    }

    async function loadTrialStatus() {
        const banner = document.getElementById('trialBanner');
        const trialText = document.getElementById('trialText');
        if (!banner || !trialText) return;
        try {
            const response = await fetch('/api/trial-status');
            const data = await response.json();
            if (!data.success) return;
            const trial = data.trial || {};
            const plan = data.plan || {};
            const planType = String(plan.plan_type || '').toLowerCase();
            const isFreePlan = planType === 'free';
            const shouldBlock = data.upgrade_required === true || (isFreePlan && trial.expired);
            if (!trial.trial_start) {
                banner.style.display = 'none';
                return;
            }
            if (shouldBlock) {
                trialText.innerHTML = '<strong>Trial ended.</strong> Please upgrade to continue.';
                banner.style.display = 'block';
                openUpgradeModal();
                return;
            }
            trialText.innerHTML = `Trial ends in <strong>${trial.days_left}</strong> day(s).`;
            banner.style.display = 'block';
        } catch (e) {
            // ignore
        }
    }

    async function loadUsageStats() {
        const widget = document.getElementById('usageWidget');
        if (!widget) return;
        const planName = document.getElementById('planNameText');
        const usageText = document.getElementById('usageText');
        const usageFill = document.getElementById('usageFill');
        try {
            const response = await fetch('/api/usage-stats');
            const data = await response.json();
            if (!data.success) return;
            const stats = data.stats || {};
            const images = stats.images || {};
            if (planName) planName.textContent = stats.plan_name || 'Plan';
            if (usageText) {
                usageText.textContent = `${images.used || 0} used / ${images.limit || 0} limit`;
            }
            if (usageFill) {
                usageFill.style.width = `${images.percentage || 0}%`;
            }
            widget.style.display = 'block';
            scheduleDiscountPopup(stats);
        } catch (e) {
            // ignore
        }
    }

    function scheduleDiscountPopup(stats) {
        const planType = (stats.plan_type || '').toLowerCase();
        if (planType !== 'free') {
            return;
        }
        const key = 'cf_discount_popup_dismissed';
        if (localStorage.getItem(key) === '1') {
            return;
        }
        setTimeout(() => {
            openDiscountModal();
        }, 10000);
    }

    async function loadUserProfile() {
        const modal = document.getElementById('profileModal');
        if (!modal) return;
        try {
            const response = await fetch('/api/user-profile');
            const data = await response.json();
            if (!data.success) return;
            if (!data.complete) {
                openProfileModal(data.profile || {});
            }
        } catch (e) {
            // ignore
        }
    }

    function initMonetizationUi() {
        loadTrialStatus();
        loadUsageStats();
        loadUserProfile();

        const discountBackdrop = document.getElementById('discountModal');
        if (discountBackdrop) {
            discountBackdrop.addEventListener('click', (event) => {
                if (event.target && event.target.id === 'discountModal') {
                    closeDiscountModal();
                }
            });
        }
    }

    window.openUpgradeModal = openUpgradeModal;
    window.closeUpgradeModal = closeUpgradeModal;
    window.closeProfileModal = closeProfileModal;
    window.saveProfileDetails = saveProfileDetails;
    window.closeDiscountModal = closeDiscountModal;

    window.addEventListener('load', () => {
        initAnalytics();
        initMonetizationUi();
    });
})();
