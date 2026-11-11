// Theme Toggle Utility — Online Auction Bid Management System
(function() {
    function getStoredTheme() {
        return localStorage.getItem('theme') || 'dark';
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        updateToggleButtons(theme);
    }

    function updateToggleButtons(theme) {
        const toggleBtns = document.querySelectorAll('.theme-toggle, #theme-toggle');
        toggleBtns.forEach(btn => {
            if (!btn) return;
            if (theme === 'dark') {
                btn.setAttribute('aria-label', 'Switch to light mode');
                btn.setAttribute('title', 'Switch to light mode');
            } else {
                btn.setAttribute('aria-label', 'Switch to dark mode');
                btn.setAttribute('title', 'Switch to dark mode');
            }
        });
    }

    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(newTheme);
    }

    function toggleThemeHandler(e) {
        e.preventDefault();
        toggleTheme();
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', () => {
        const currentTheme = getStoredTheme();
        applyTheme(currentTheme);

        const toggleBtns = document.querySelectorAll('.theme-toggle, #theme-toggle');
        toggleBtns.forEach(btn => {
            btn.addEventListener('click', toggleThemeHandler);
        });
    });

    window.toggleTheme = toggleTheme;
})();
