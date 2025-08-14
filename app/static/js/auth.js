// Authentication utilities

class AuthManager {
    constructor() {
        this.token = localStorage.getItem('access_token');
        this.checkAuthStatus();
    }

    checkAuthStatus() {
        // Check if we're on login/register pages
        const currentPath = window.location.pathname;
        if (currentPath === '/login' || currentPath === '/register') {
            return;
        }

        // If no token and not on auth pages, redirect to login
        if (!this.token) {
            this.redirectToLogin();
            return;
        }

        // Verify token is still valid
        this.verifyToken();
    }

    async verifyToken() {
        try {
            const response = await fetch('/api/auth/me', {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });

            if (!response.ok) {
                throw new Error('Token invalid');
            }

            const user = await response.json();
            this.updateUserInfo(user);
        } catch (error) {
            console.error('Token verification failed:', error);
            this.logout();
        }
    }

    async login(email, password) {
        try {
            const formData = new FormData();
            formData.append('username', email);
            formData.append('password', password);

            const response = await fetch('/token', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Login failed');
            }

            const data = await response.json();
            this.token = data.access_token;
            localStorage.setItem('access_token', this.token);
            
            // Redirect to dashboard
            window.location.href = '/';
            
            return { success: true };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    async register(email, username, fullName, password) {
        try {
            const response = await fetch('/api/auth/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email,
                    username,
                    full_name: fullName,
                    password
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Registration failed');
            }

            const data = await response.json();
            this.token = data.access_token;
            localStorage.setItem('access_token', this.token);
            
            // Redirect to dashboard
            window.location.href = '/';
            
            return { success: true };
        } catch (error) {
            return { success: false, error: error.message };
        }
    }

    logout() {
        this.token = null;
        localStorage.removeItem('access_token');
        this.redirectToLogin();
    }

    redirectToLogin() {
        if (window.location.pathname !== '/login') {
            window.location.href = '/login';
        }
    }

    updateUserInfo(user) {
        // Update user info in the UI
        const userNameElement = document.getElementById('user-name');
        const userEmailElement = document.getElementById('user-email');
        
        if (userNameElement) {
            userNameElement.textContent = user.full_name || user.username;
        }
        if (userEmailElement) {
            userEmailElement.textContent = user.email;
        }
    }

    getAuthHeaders() {
        return {
            'Authorization': `Bearer ${this.token}`,
            'Content-Type': 'application/json'
        };
    }

    async makeAuthenticatedRequest(url, options = {}) {
        const headers = {
            ...this.getAuthHeaders(),
            ...options.headers
        };

        const response = await fetch(url, {
            ...options,
            headers
        });

        if (response.status === 401) {
            this.logout();
            throw new Error('Authentication required');
        }

        return response;
    }
}

// Initialize auth manager
const authManager = new AuthManager();

// Login form handler
function setupLoginForm() {
    const form = document.getElementById('login-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const submitBtn = document.getElementById('submit-btn');
        const errorDiv = document.getElementById('error-message');

        // Clear previous errors
        errorDiv.classList.add('hidden');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<div class="loading-spinner"></div> Signing in...';

        const result = await authManager.login(email, password);

        if (!result.success) {
            errorDiv.textContent = result.error;
            errorDiv.classList.remove('hidden');
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Sign In';
        }
    });
}

// Register form handler
function setupRegisterForm() {
    const form = document.getElementById('register-form');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const email = document.getElementById('email').value;
        const username = document.getElementById('username').value;
        const fullName = document.getElementById('full-name').value;
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirm-password').value;
        const submitBtn = document.getElementById('submit-btn');
        const errorDiv = document.getElementById('error-message');

        // Clear previous errors
        errorDiv.classList.add('hidden');

        // Validate passwords match
        if (password !== confirmPassword) {
            errorDiv.textContent = 'Passwords do not match';
            errorDiv.classList.remove('hidden');
            return;
        }

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<div class="loading-spinner"></div> Creating account...';

        const result = await authManager.register(email, username, fullName, password);

        if (!result.success) {
            errorDiv.textContent = result.error;
            errorDiv.classList.remove('hidden');
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Create Account';
        }
    });
}

// Logout handler
function setupLogout() {
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            authManager.logout();
        });
    }
}

// Initialize auth forms when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    setupLoginForm();
    setupRegisterForm();
    setupLogout();
});
