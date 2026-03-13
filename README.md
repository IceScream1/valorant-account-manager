# 🎮 VALORANT Account Manager (v5)

A professional, lightweight tool designed for players with multiple Valorant accounts. Switch between accounts seamlessly, preserve login sessions, and manage your credentials securely.

## 🌟 Key Features
- **Session Switching:** Swap between accounts without re-entering credentials or auth codes. Snapshot your Riot Client Data once, and switch instantly.
- **Smart Clipboard:** Click an account to copy the username. Paste it into the Riot Client, and the tool automatically swaps your clipboard to the password for the second paste.
- **Nicknames & Favorites:** Keep your accounts organized with custom nicknames (safe for stream) and star your most used accounts.
- **Auto-Launch:** Relaunch the Riot Client or Valorant automatically after a session swap.
- **Secure Backups:** Automatic periodic backups of your accounts file to prevent data loss.
- **Dual Themes:** Choose between the classic "Valorant" aesthetic and a "Cozy" warm theme.
- **Lightweight:** Zero external dependencies—runs on standard Python 3.10+.

## 🛠️ Installation
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/IceScream1/valorant-account-manager.git
    cd valorant-account-manager
    ```
2.  **Run the application:**
    ```bash
    python main.py
    ```

## 🚀 How to Use
1.  **Add your accounts** using the `+ Add` button.
2.  **Save a Session:** Log into an account normally in the Riot Client, then click `💾 Save` in this tool to capture the session data.
3.  **Switch Sessions:** In the future, just click `⇄ Switch` to swap to that account instantly without logging in manually.

## ⚠️ Security Warning
Your credentials and session data are stored locally in your **Documents/ValorantAccountManager** folder. **Never share this folder** or your `accounts.json` file with anyone. This repository includes a `.gitignore` to prevent these local files from being uploaded to GitHub.

## ⚙️ Requirements
- Windows 10/11
- Python 3.10+
- (No external `pip` packages required!)
