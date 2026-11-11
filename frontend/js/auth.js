// Authentication state and UI logic
document.addEventListener('DOMContentLoaded', async () => {
    // 1. Update navigation based on auth state
    const authActions = document.getElementById('auth-actions');
    const mobileNavLinks = document.querySelector('.mobile-nav-links');
    
    // Some pages might not have these elements or we need to handle them carefully
    if (authActions || mobileNavLinks) {
        const authData = await api.getMe();
        updateNavUI(authData);
    }

    // 2. Handle Login Form
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('login-btn');
            const msg = document.getElementById('login-message');
            const email = document.getElementById('email').value.trim();
            const password = document.getElementById('password').value;

            btn.disabled = true;
            btn.textContent = 'Signing in...';

            const result = await api.login(email, password);
            if (result.success) {
                window.location.href = result.user.role === 'ADMIN' ? 'admin.html' : 'index.html';
            } else {
                showMessage(msg, result.error || 'Login failed', 'error');
                btn.disabled = false;
                btn.textContent = 'Sign In';
            }
        });
    }

    // 3. Handle Admin Login Form
    const adminLoginForm = document.getElementById('admin-login-form');
    if (adminLoginForm) {
        adminLoginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('login-btn');
            const msg = document.getElementById('login-message');
            const email = document.getElementById('email').value.trim();
            const password = document.getElementById('password').value;

            btn.disabled = true;
            btn.textContent = 'Authenticating...';

            const result = await api.adminLogin(email, password);
            if (result.success) {
                window.location.href = 'admin.html';
            } else {
                showMessage(msg, result.error || 'Authentication failed', 'error');
                btn.disabled = false;
                btn.textContent = 'Secure Login';
            }
        });
    }

    // 4. Handle Register Form
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('register-btn');
            const msg = document.getElementById('register-message');
            
            const username = document.getElementById('username').value.trim();
            const email = document.getElementById('email').value.trim();
            const password = document.getElementById('password').value;
            const confirm_password = document.getElementById('confirm-password').value;

            if (password !== confirm_password) {
                showMessage(msg, 'Passwords do not match', 'error');
                return;
            }

            btn.disabled = true;
            btn.textContent = 'Creating account...';

            const result = await api.register({ username, email, password, confirm_password });
            if (result.success) {
                showMessage(msg, 'Registration successful! Redirecting to login...', 'success');
                setTimeout(() => {
                    window.location.href = 'login.html';
                }, 1500);
            } else {
                showMessage(msg, result.error || 'Registration failed', 'error');
                btn.disabled = false;
                btn.textContent = 'Register';
            }
        });
    }

    // 5. Protect Admin Page
    // If we are on admin.html, redirect if not admin
    if (window.location.pathname.endsWith('admin.html')) {
        const authData = await api.getMe();
        if (!authData || !authData.authenticated || authData.user.role !== 'ADMIN') {
            window.location.href = 'admin-login.html';
        }
    }
});

function updateNavUI(authData) {
    const authActions = document.getElementById('auth-actions');
    const mobileNavLinks = document.querySelector('.mobile-nav-links');
    
    if (authData && authData.authenticated) {
        const role = authData.user.role;
        const username = authData.user.username;

        if (authActions) {
            authActions.innerHTML = `
                <span class="nav-link" style="color:var(--color-text-2); margin-right: 0.5rem;">Hi, ${username}</span>
                <a href="profile.html" class="nav-link btn btn-secondary btn-sm" style="margin-right: 0.5rem;">Profile</a>
                ${role === 'ADMIN' ? '<a href="admin.html" class="nav-link btn btn-secondary btn-sm" style="margin-right: 0.5rem;">Admin Dashboard</a>' : ''}
                <button onclick="handleLogout()" class="nav-link btn btn-outline btn-sm" style="border: 1px solid var(--color-border); background: transparent; cursor: pointer;">Logout</button>
            `;
        }

        if (mobileNavLinks) {
            // Re-render mobile links safely
            const currentLinksHtml = `
                <a href="index.html" class="mobile-nav-link">Auctions</a>
                <a href="about.html#how-it-works" class="mobile-nav-link">How It Works</a>
                <a href="about.html" class="mobile-nav-link">About</a>
            `;
            
            mobileNavLinks.innerHTML = currentLinksHtml + `
                <a href="profile.html" class="mobile-nav-link">Profile</a>
                ${role === 'ADMIN' ? '<a href="admin.html" class="mobile-nav-link">Admin Dashboard</a>' : ''}
                <div style="padding: 1rem 1.5rem; color: var(--color-text-2); font-size: 0.875rem;">Logged in as ${username}</div>
                <button onclick="handleLogout()" class="mobile-nav-link" style="width: 100%; text-align: left; background: none; border: none; cursor: pointer;">Logout</button>
            `;
        }
    } else {
        if (authActions && !authActions.innerHTML.includes('Login')) {
            authActions.innerHTML = `
                <a href="login.html" class="nav-link btn btn-secondary btn-sm">Login</a>
                <a href="register.html" class="nav-link btn btn-primary btn-sm">Register</a>
            `;
        }
        if (mobileNavLinks && !mobileNavLinks.innerHTML.includes('Login')) {
            const currentLinksHtml = `
                <a href="index.html" class="mobile-nav-link">Auctions</a>
                <a href="about.html#how-it-works" class="mobile-nav-link">How It Works</a>
                <a href="about.html" class="mobile-nav-link">About</a>
            `;
            mobileNavLinks.innerHTML = currentLinksHtml + `
                <a href="login.html" class="mobile-nav-link">Login</a>
                <a href="register.html" class="mobile-nav-link">Register</a>
            `;
        }
    }
}

async function handleLogout() {
    await api.logout();
    window.location.href = 'index.html';
}

function showMessage(container, text, type) {
    if (!container) return;
    container.innerHTML = `<div class="alert alert-${type}">${text}</div>`;
    if (type !== 'success') {
        setTimeout(() => {
            if (container && container.parentNode) container.innerHTML = '';
        }, 5000);
    }
}
