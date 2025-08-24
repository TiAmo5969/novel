// Reading Experience Enhancements
class ReadingExperience {
    constructor() {
        this.currentFontSize = 18;
        this.isDarkMode = false;
        this.isFullscreen = false;
        this.init();
    }

    init() {
        this.setupReadingProgress();
        this.setupFontControls();
        this.setupDarkMode();
        this.setupFullscreen();
        this.setupKeyboardShortcuts();
        this.setupAutoSave();
        this.setupReadingAnalytics();
    }

    setupReadingProgress() {
        const progressBar = document.getElementById('reading-progress');
        if (!progressBar) return;

        window.addEventListener('scroll', () => {
            const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
            const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
            const scrolled = (winScroll / height) * 100;
            progressBar.style.width = scrolled + '%';
        });
    }

    setupFontControls() {
        const content = document.getElementById('chapter-content');
        const fontSizeDisplay = document.getElementById('font-size-display');
        const increaseBtn = document.getElementById('font-size-increase');
        const decreaseBtn = document.getElementById('font-size-decrease');

        if (!content || !fontSizeDisplay) return;

        // Load saved font size
        const savedFontSize = localStorage.getItem('fontSize');
        if (savedFontSize) {
            this.currentFontSize = parseInt(savedFontSize);
            this.updateFontSize();
        }

        if (increaseBtn) {
            increaseBtn.addEventListener('click', () => {
                if (this.currentFontSize < 24) {
                    this.currentFontSize += 2;
                    this.updateFontSize();
                    this.saveFontSize();
                }
            });
        }

        if (decreaseBtn) {
            decreaseBtn.addEventListener('click', () => {
                if (this.currentFontSize > 14) {
                    this.currentFontSize -= 2;
                    this.updateFontSize();
                    this.saveFontSize();
                }
            });
        }

        this.updateFontSize();
    }

    updateFontSize() {
        const content = document.getElementById('chapter-content');
        const fontSizeDisplay = document.getElementById('font-size-display');
        
        if (content) {
            content.style.fontSize = this.currentFontSize + 'px';
        }
        
        if (fontSizeDisplay) {
            fontSizeDisplay.textContent = this.currentFontSize + 'px';
        }
    }

    saveFontSize() {
        localStorage.setItem('fontSize', this.currentFontSize);
    }

    setupDarkMode() {
        const toggleBtn = document.getElementById('toggle-dark-mode');
        if (!toggleBtn) return;

        // Check for saved theme preference
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            this.isDarkMode = true;
            document.documentElement.classList.add('dark');
        }

        toggleBtn.addEventListener('click', () => {
            this.isDarkMode = !this.isDarkMode;
            if (this.isDarkMode) {
                document.documentElement.classList.add('dark');
                localStorage.setItem('theme', 'dark');
            } else {
                document.documentElement.classList.remove('dark');
                localStorage.setItem('theme', 'light');
            }
        });
    }

    setupFullscreen() {
        const toggleBtn = document.getElementById('toggle-fullscreen');
        if (!toggleBtn) return;

        toggleBtn.addEventListener('click', () => {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().then(() => {
                    this.isFullscreen = true;
                });
            } else {
                document.exitFullscreen().then(() => {
                    this.isFullscreen = false;
                });
            }
        });
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Don't trigger shortcuts when typing in input fields
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }

            switch(e.key) {
                case 'ArrowLeft':
                    this.navigateChapter('prev');
                    break;
                case 'ArrowRight':
                    this.navigateChapter('next');
                    break;
                case '+':
                case '=':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.increaseFontSize();
                    }
                    break;
                case '-':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.decreaseFontSize();
                    }
                    break;
                case 'd':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.toggleDarkMode();
                    }
                    break;
                case 'f':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.toggleFullscreen();
                    }
                    break;
            }
        });
    }

    navigateChapter(direction) {
        const prevLink = document.querySelector('a[href*="chapter"][href*="prev"]');
        const nextLink = document.querySelector('a[href*="chapter"][href*="next"]');

        if (direction === 'prev' && prevLink) {
            window.location.href = prevLink.href;
        } else if (direction === 'next' && nextLink) {
            window.location.href = nextLink.href;
        }
    }

    increaseFontSize() {
        if (this.currentFontSize < 24) {
            this.currentFontSize += 2;
            this.updateFontSize();
            this.saveFontSize();
        }
    }

    decreaseFontSize() {
        if (this.currentFontSize > 14) {
            this.currentFontSize -= 2;
            this.updateFontSize();
            this.saveFontSize();
        }
    }

    toggleDarkMode() {
        const toggleBtn = document.getElementById('toggle-dark-mode');
        if (toggleBtn) {
            toggleBtn.click();
        }
    }

    toggleFullscreen() {
        const toggleBtn = document.getElementById('toggle-fullscreen');
        if (toggleBtn) {
            toggleBtn.click();
        }
    }

    setupAutoSave() {
        // Auto-save reading position
        window.addEventListener('beforeunload', () => {
            const scrollPosition = window.pageYOffset;
            const chapterId = this.getChapterId();
            if (chapterId) {
                localStorage.setItem(`reading-position-${chapterId}`, scrollPosition);
            }
        });

        // Restore reading position
        window.addEventListener('load', () => {
            const chapterId = this.getChapterId();
            if (chapterId) {
                const savedPosition = localStorage.getItem(`reading-position-${chapterId}`);
                if (savedPosition) {
                    setTimeout(() => {
                        window.scrollTo(0, parseInt(savedPosition));
                    }, 100);
                }
            }
        });
    }

    getChapterId() {
        const path = window.location.pathname;
        const match = path.match(/\/chapter\/(\d+)/);
        return match ? match[1] : null;
    }

    setupReadingAnalytics() {
        let startTime = Date.now();
        let readingTime = 0;
        let isReading = true;

        // Track reading time
        const trackReading = () => {
            if (isReading) {
                readingTime += 1000; // 1 second
            }
        };

        const interval = setInterval(trackReading, 1000);

        // Pause tracking when user is not active
        document.addEventListener('visibilitychange', () => {
            isReading = !document.hidden;
        });

        // Send analytics when leaving page
        window.addEventListener('beforeunload', () => {
            clearInterval(interval);
            this.sendReadingAnalytics(readingTime);
        });
    }

    sendReadingAnalytics(readingTime) {
        // Send to Google Analytics if available
        if (typeof gtag !== 'undefined') {
            gtag('event', 'reading_time', {
                'event_category': 'engagement',
                'event_label': 'chapter_reading',
                'value': Math.round(readingTime / 1000) // Convert to seconds
            });
        }
    }
}

// Initialize reading experience when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new ReadingExperience();
});

// Enhanced mobile experience
class MobileReadingExperience {
    constructor() {
        this.setupMobileGestures();
        this.setupMobileOptimizations();
    }

    setupMobileGestures() {
        let startX = 0;
        let startY = 0;

        document.addEventListener('touchstart', (e) => {
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
        });

        document.addEventListener('touchend', (e) => {
            if (!startX || !startY) return;

            const endX = e.changedTouches[0].clientX;
            const endY = e.changedTouches[0].clientY;

            const diffX = startX - endX;
            const diffY = startY - endY;

            // Minimum swipe distance
            if (Math.abs(diffX) > 50 && Math.abs(diffY) < 100) {
                if (diffX > 0) {
                    // Swipe left - next chapter
                    this.navigateChapter('next');
                } else {
                    // Swipe right - previous chapter
                    this.navigateChapter('prev');
                }
            }

            startX = 0;
            startY = 0;
        });
    }

    navigateChapter(direction) {
        const prevLink = document.querySelector('a[href*="chapter"][href*="prev"]');
        const nextLink = document.querySelector('a[href*="chapter"][href*="next"]');

        if (direction === 'prev' && prevLink) {
            window.location.href = prevLink.href;
        } else if (direction === 'next' && nextLink) {
            window.location.href = nextLink.href;
        }
    }

    setupMobileOptimizations() {
        // Optimize for mobile reading
        if (window.innerWidth <= 768) {
            const content = document.getElementById('chapter-content');
            if (content) {
                content.style.fontSize = '16px';
                content.style.lineHeight = '1.6';
            }
        }
    }
}

// Initialize mobile experience
if ('ontouchstart' in window) {
    document.addEventListener('DOMContentLoaded', () => {
        new MobileReadingExperience();
    });
} 