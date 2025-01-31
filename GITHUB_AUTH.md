# GitHub Authentication Guide

## Setting Up GitHub Authentication with Personal Access Token (PAT)

### 1. Generate Personal Access Token
1. Go to GitHub.com → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a descriptive name (e.g., "Local Development Machine")
4. Set an expiration date (e.g., 90 days)
5. Select scopes:
   - At minimum, check `repo` for repository access
   - Add other scopes as needed (e.g., `workflow` for GitHub Actions)
6. Click "Generate token"
7. **IMPORTANT**: Copy the token immediately - you won't be able to see it again!
8. Save the token in your password keeper software (e.g., Bitwarden or 1Password). I use Bitwarden, and make a Note entry "git push" and store the token in the Note (as the only thing in the Note, so copy/paste is easy).

### 2. Create GitHub Repository
1. Go to GitHub.com and click the "+" in the top right, then "New repository"
2. Name your repository
3. Choose public or private
4. Do NOT initialize with README, license, or .gitignore if you already have these files locally
5. Click "Create repository"
6. GitHub will show you setup instructions - use the HTTPS URL it provides

### 3. Configure Local Repository

#### New Repository Setup
```bash
# Initialize repository
git init

# Add and commit your files
git add .
git commit -m "Initial commit"

# Make a repository in GitHub and add remote using the HTTPS URL GitHub provides:
git remote add origin https://github.com/USERNAME/REPOSITORY.git

# Push and set upstream
git push --set-upstream origin main
```

When prompted:
- Username: your GitHub email
- Password: paste your Personal Access Token from your password manager (not your GitHub password)

#### Store Credentials (Optional)
To avoid entering credentials each time:
```bash
git config --global credential.helper store
```

### 4. Fixing SSH Authentication Issues

If git asks for SSH credentials (e.g., "Enter passphrase for key '/home/USER/.ssh/github'"), you're using SSH authentication instead of HTTPS. Here's how to fix it:

1. Check your current remote:
```bash
git remote -v
```

2. If it shows an SSH URL (git@github.com:...), remove it:
```bash
git remote remove origin
```

3. Add the correct HTTPS remote:
```bash
git remote add origin https://github.com/USERNAME/REPOSITORY.git
```

4. Push using the new remote:
```bash
git push --set-upstream origin main
```

### Common Issues and Solutions

1. **Wrong Password Error**: If you get authentication errors, make sure you're using your Personal Access Token as the password, not your GitHub account password.

2. **Token Expiration**: Personal Access Tokens can expire. If authentication suddenly fails:
   - Check token expiration in GitHub settings
   - Generate a new token if needed
   - Update stored credentials
   - Update the token in your password manager
   - If you use credential.helper store, you'll need to enter the new token on your next push

3. **Multiple Accounts**: If you have multiple GitHub accounts, you can use different Personal Access Tokens for each repository:
```bash
git config credential.helper store --local  # Store credentials per repository
```

### Best Practices

1. **Token Security**:
   - Never share or expose your Personal Access Token
   - Use the minimum required scopes for your token
   - Set an expiration date
   - Rotate tokens periodically

2. **Credential Storage**:
   - Consider using a credential manager (e.g., Git Credential Manager)
   - Review stored credentials periodically
   - Remove old or unused credentials

3. **Repository URLs**:
   - Always use HTTPS URLs for new repositories
   - Update existing repositories to use HTTPS if they're using SSH
