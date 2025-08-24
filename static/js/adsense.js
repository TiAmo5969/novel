// AdSense Optimization Script
class AdSenseOptimizer {
    constructor() {
        this.adContainers = document.querySelectorAll('.ad-container');
        this.init();
    }

    init() {
        this.setupAdLoading();
        this.setupAdPlacement();
        this.setupAdAnalytics();
        this.setupAdBlockDetection();
    }

    setupAdLoading() {
        // Optimize ad loading for better user experience
        this.adContainers.forEach(container => {
            // Add loading state
            container.innerHTML = '<div class="ad-loading">Loading advertisement...</div>';
            
            // Add CSS for loading state
            const style = document.createElement('style');
            style.textContent = `
                .ad-loading {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 90px;
                    background: #f8fafc;
                    border-radius: 8px;
                    color: #6b7280;
                    font-size: 14px;
                }
                .dark .ad-loading {
                    background: #1e293b;
                    color: #9ca3af;
                }
                .ad-container {
                    margin: 2rem 0;
                    text-align: center;
                    min-height: 90px;
                    background: #f8fafc;
                    border-radius: 8px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .dark .ad-container {
                    background: #1e293b;
                }
            `;
            document.head.appendChild(style);
        });
    }

    setupAdPlacement() {
        // Ensure ads don't interfere with reading experience
        const readingContent = document.getElementById('chapter-content');
        if (readingContent) {
            // Add spacing around ads in reading content
            const adSpacing = document.createElement('style');
            adSpacing.textContent = `
                .chapter-content .ad-container {
                    margin: 3rem 0;
                    page-break-inside: avoid;
                }
                @media print {
                    .ad-container {
                        display: none !important;
                    }
                }
            `;
            document.head.appendChild(adSpacing);
        }
    }

    setupAdAnalytics() {
        // Track ad performance
        if (typeof gtag !== 'undefined') {
            // Track ad impressions
            this.adContainers.forEach((container, index) => {
                const observer = new IntersectionObserver((entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            gtag('event', 'ad_impression', {
                                'event_category': 'advertising',
                                'event_label': `ad_container_${index}`,
                                'value': 1
                            });
                        }
                    });
                });
                observer.observe(container);
            });
        }
    }

    setupAdBlockDetection() {
        // Detect ad blockers and show alternative content
        setTimeout(() => {
            const adElements = document.querySelectorAll('ins.adsbygoogle');
            let adBlockDetected = false;

            adElements.forEach(ad => {
                if (ad.offsetHeight === 0 || ad.offsetWidth === 0) {
                    adBlockDetected = true;
                }
            });

            if (adBlockDetected) {
                this.showAdBlockMessage();
            }
        }, 3000);
    }

    showAdBlockMessage() {
        const message = document.createElement('div');
        message.className = 'ad-block-message';
        message.innerHTML = `
            <div class="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4 mb-4">
                <div class="flex items-center">
                    <svg class="w-5 h-5 text-yellow-600 mr-2" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
                    </svg>
                    <p class="text-yellow-800 dark:text-yellow-200 text-sm">
                        We notice you're using an ad blocker. Our site is free to use and ads help support our service. 
                        Please consider disabling your ad blocker to support us.
                    </p>
                </div>
            </div>
        `;

        // Insert message after the first ad container
        const firstAdContainer = document.querySelector('.ad-container');
        if (firstAdContainer) {
            firstAdContainer.parentNode.insertBefore(message, firstAdContainer.nextSibling);
        }
    }
}

// AdSense Loading Optimization
class AdSenseLoader {
    constructor() {
        this.loadedAds = new Set();
        this.init();
    }

    init() {
        this.setupLazyLoading();
        this.setupPerformanceOptimization();
    }

    setupLazyLoading() {
        // Load ads only when they come into view
        const adObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && !this.loadedAds.has(entry.target)) {
                    this.loadAd(entry.target);
                    this.loadedAds.add(entry.target);
                }
            });
        }, {
            rootMargin: '50px'
        });

        // Observe all ad containers
        document.querySelectorAll('.ad-container').forEach(container => {
            adObserver.observe(container);
        });
    }

    loadAd(container) {
        // Remove loading state
        const loadingElement = container.querySelector('.ad-loading');
        if (loadingElement) {
            loadingElement.remove();
        }

        // Initialize AdSense
        if (typeof adsbygoogle !== 'undefined') {
            try {
                (adsbygoogle = window.adsbygoogle || []).push({});
            } catch (error) {
                console.warn('AdSense loading error:', error);
            }
        }
    }

    setupPerformanceOptimization() {
        // Preload AdSense script for better performance
        const preloadLink = document.createElement('link');
        preloadLink.rel = 'preload';
        preloadLink.as = 'script';
        preloadLink.href = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2786216806192691';
        document.head.appendChild(preloadLink);
    }
}

// Mobile Ad Optimization
class MobileAdOptimizer {
    constructor() {
        this.isMobile = window.innerWidth <= 768;
        this.init();
    }

    init() {
        if (this.isMobile) {
            this.optimizeForMobile();
        }
    }

    optimizeForMobile() {
        // Adjust ad container sizes for mobile
        const mobileAdStyle = document.createElement('style');
        mobileAdStyle.textContent = `
            @media (max-width: 768px) {
                .ad-container {
                    margin: 1rem 0;
                    min-height: 60px;
                }
                .ad-loading {
                    height: 60px;
                    font-size: 12px;
                }
            }
        `;
        document.head.appendChild(mobileAdStyle);
    }
}

// Initialize all ad optimizations when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new AdSenseOptimizer();
    new AdSenseLoader();
    new MobileAdOptimizer();
});

// AdSense Error Handling
window.addEventListener('error', (event) => {
    if (event.message.includes('adsbygoogle')) {
        console.warn('AdSense error detected:', event.message);
        
        // Track error in analytics
        if (typeof gtag !== 'undefined') {
            gtag('event', 'adsense_error', {
                'event_category': 'advertising',
                'event_label': 'adsense_loading_error',
                'value': 1
            });
        }
    }
});

// AdSense Success Tracking
const originalPush = window.adsbygoogle?.push;
if (originalPush) {
    window.adsbygoogle.push = function(...args) {
        // Track successful ad loads
        if (typeof gtag !== 'undefined') {
            gtag('event', 'adsense_load', {
                'event_category': 'advertising',
                'event_label': 'adsense_successful_load',
                'value': 1
            });
        }
        
        return originalPush.apply(this, args);
    };
} 