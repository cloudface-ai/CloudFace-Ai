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
})();
