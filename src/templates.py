"""
HTML and frontend templates for:
- Admin console (/admin, login required)
- Lobby QR Code tab (/qr or /lobby)
- Player Mobile Interface (/join)
- Public Display (/display)
"""

from typing import Optional

def get_admin_html(port: int, lan_ip: str, base_url: Optional[str] = None) -> str:
    join_url = f"{base_url.rstrip('/')}/join" if base_url else f"http://{lan_ip}:{port}/join"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Console - One of These People Is Not Lying</title>
    <link rel="stylesheet" href="/static/app.css">
    <style>
        :root {{
            --bg-dark: var(--ink);
            --bg-card: var(--ink-2);
            --bg-card-hover: #201d1a;
            --border: #2e2a25;
            --primary: #e9e4d8;
            --primary-hover: #d8d0bd;
            --success: #5ea67e;
            --danger: #e0675a;
            --warning: #c99236;
            --guesser-color: #d9a441;
            --truth-color: #7cc19a;
            --liar-color: #e47f73;
            --text-main: #ece7dc;
            --text-muted: #a39b8c;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: var(--font-ui);
        }}
        body {{
            background-color: var(--bg-dark);
            color: var(--text-main);
            min-height: 100vh;
            padding: 20px;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .header-left {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .badge-logo {{
            background: var(--paper);
            color: var(--paper-ink);
            padding: 8px 12px;
            border-radius: 4px;
            font: 600 0.85rem var(--font-mono);
            letter-spacing: 0.16em;
            transform: rotate(-2deg);
        }}
        .player-score {{ white-space: nowrap; }}
        .title-group h1 {{
            font-size: 1.4rem;
            font-weight: 700;
        }}
        .title-group p {{
            font-size: 0.85rem;
            color: var(--text-muted);
        }}
        .header-actions {{
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .badge {{
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .badge-live {{
            background: rgba(94,166,126, 0.2);
            color: var(--success);
            border: 1px solid var(--success);
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .dot-pulse {{
            width: 8px;
            height: 8px;
            background: var(--success);
            border-radius: 50%;
            box-shadow: 0 0 8px var(--success);
        }}
        .btn {{
            background-color: var(--bg-card);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 0.88rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            text-decoration: none;
        }}
        .btn:hover {{
            background-color: var(--bg-card-hover);
            border-color: #4a443b;
        }}
        .btn-primary {{
            background: var(--paper);
            border: 1px solid var(--paper);
            color: var(--paper-ink);
        }}
        .btn-primary:hover {{ background: #fff8ea; border-color: #fff8ea; }}
        .btn-qr {{
            background: transparent;
            border: 1px solid rgba(124,193,154, 0.55);
            color: var(--truth);
        }}
        .btn-danger {{
            background: transparent;
            border: 1px solid rgba(224,103,90, 0.55);
            color: var(--liar);
        }}
        .btn-danger:hover {{ background: rgba(224,103,90, 0.12); border-color: var(--liar); }}
        .btn-warning {{
            background: var(--guesser);
            border: 1px solid var(--guesser);
            color: var(--paper-ink);
            font-weight: 700;
        }}
        .btn-warning:hover {{ background: #e8b95c; border-color: #e8b95c; }}
        .btn-qr:hover {{ background: rgba(124,193,154, 0.12); border-color: var(--truth); }}
        .pack-list {{ display: flex; flex-wrap: wrap; gap: 8px; }}
        .pack-item {{
            display: flex; align-items: center; gap: 8px; cursor: pointer;
            background: #201d1a; border: 1px solid #36312b; border-radius: 8px; padding: 6px 10px;
            font-size: 0.82rem; color: #e2dccf;
        }}
        .pack-item input {{ width: 16px; height: 16px; margin: 0; flex: none; }}
        .pack-count {{ color: #a39b8c; font-size: 0.75rem; white-space: nowrap; }}
        /* 3-way role-mode switch: native radios, a thumb slides under the checked one */
        .tri {{ position: relative; display: grid; grid-template-columns: repeat(3, 1fr); margin: 0; padding: 3px;
            border: 1px solid #3a352e; border-radius: 999px; background: #171513; min-width: 300px; }}
        .tri legend {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }}
        .tri input {{ position: absolute; opacity: 0; pointer-events: none; }}
        .tri label {{ position: relative; z-index: 1; text-align: center; padding: 5px 10px; font-size: 0.8rem; font-weight: 700;
            color: #a39b8c; cursor: pointer; border-radius: 999px; transition: color .2s; white-space: nowrap; }}
        .tri::before {{ content: ""; position: absolute; top: 3px; bottom: 3px; left: 3px; width: calc((100% - 6px) / 3);
            border-radius: 999px; background: #36312b; transition: transform .22s cubic-bezier(.3,.7,.2,1), background .22s; }}
        .tri:has(input:nth-of-type(2):checked)::before {{ transform: translateX(100%); }}
        .tri:has(input:nth-of-type(3):checked)::before {{ transform: translateX(200%); }}
        .tri:has(#rm-one_truth:checked)::before {{ background: rgba(124,193,154, 0.25); }}
        .tri:has(#mm-off:checked)::before {{ background: rgba(255,255,255, 0.08); }}
        .match-status {{ font-size: 0.78rem; color: #a39b8c; }}
        .match-status.bad {{ color: #e47f73; }}
        .tri:has(#rm-one_liar:checked)::before {{ background: rgba(228,127,115, 0.25); }}
        .tri input:checked + label {{ color: #ece7dc; }}
        .tri input:focus-visible + label {{ outline: 2px solid #d9a441; outline-offset: 1px; }}
        .role-count-off {{ opacity: 0.45; }}
        .btn-sm {{
            padding: 5px 10px;
            font-size: 0.8rem;
        }}

        .stepper {{
            display: flex;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 6px;
            margin-bottom: 24px;
            overflow-x: auto;
        }}
        .step {{
            flex: 1;
            text-align: center;
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-muted);
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
        }}
        .step.active {{
            background: rgba(233,228,216, 0.25);
            color: #e9e4d8;
            border: 1px solid rgba(233,228,216, 0.4);
        }}

        .main-grid {{
            display: grid;
            grid-template-columns: 1.25fr 0.75fr;
            gap: 20px;
        }}
        .main-grid > div, .card {{ min-width: 0; }}
        @media (max-width: 950px) {{
            .main-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        @media (max-width: 600px) {{
            .stepper {{ flex-wrap: wrap; }}
            .step {{ flex: 1 1 30%; padding: 8px 6px; font-size: 0.8rem; }}
        }}

        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 20px;
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
        }}
        .card-title {{
            font-size: 1.05rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .dossier {{
            background: #1a1816;
            border: 1px solid #c9bfa8;
            position: relative;
        }}
        .dossier-title {{ color: var(--liar-color); font-size: 1.4rem; font-weight: 800; letter-spacing: 1.5px; }}

        .guesser-banner {{
            background: rgba(217,164,65, 0.15);
            border-left: 4px solid var(--guesser-color);
            padding: 12px;
            border-radius: 0 8px 8px 0;
            margin: 12px 0;
        }}
        .guesser-name {{
            font-size: 1.2rem;
            font-weight: 800;
            color: var(--guesser-color);
        }}

        .truth-banner {{
            background: rgba(94,166,126, 0.15);
            border-left: 4px solid var(--truth-color);
            padding: 12px;
            border-radius: 0 8px 8px 0;
            margin: 12px 0;
        }}
        .truth-person-name {{
            font-size: 1.2rem;
            font-weight: 800;
            color: var(--truth-color);
        }}

        .liar-card {{
            background: rgba(224,103,90, 0.08);
            border-left: 4px solid var(--liar-color);
            padding: 10px 14px;
            border-radius: 0 8px 8px 0;
            margin-bottom: 10px;
        }}

        .secret-blur {{
            filter: blur(6px);
            transition: filter 0.2s ease;
            user-select: none;
        }}
        .secret-blur.revealed {{
            filter: none;
            user-select: text;
        }}

        .player-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #171513;
            border: 1px solid #201d1a;
            padding: 10px 14px;
            border-radius: 8px;
            margin-bottom: 8px;
            transition: all 0.2s ease;
        }}
        .player-row.is-guesser {{
            border-color: rgba(217,164,65, 0.5);
            background: rgba(217,164,65, 0.08);
        }}
        .player-row.is-truth {{
            border-color: rgba(124,193,154, 0.5);
            background: rgba(94,166,126, 0.08);
        }}
        .player-info {{
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .player-name {{
            font-weight: 600;
            font-size: 0.95rem;
        }}
        .role-select {{
            background: #201d1a;
            color: var(--text);
            border: 1px solid #36312b;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.78rem;
            font-weight: 600;
            cursor: pointer;
        }}
        .role-select:focus {{
            border-color: var(--primary);
        }}
        .roster-table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
        .roster-table th {{ text-align: left; font: 600 0.68rem var(--font-mono); letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); padding: 6px 6px; border-bottom: 1px solid var(--line); }}
        .roster-table td {{ padding: 7px 6px; border-bottom: 1px solid var(--line-soft); vertical-align: middle; }}
        .roster-table tr.is-guesser td:first-child {{ box-shadow: inset 3px 0 0 var(--guesser); }}
        .roster-table tr.is-truth td:first-child {{ box-shadow: inset 3px 0 0 var(--truth); }}
        .roster-table .pname {{ font-weight: 650; overflow-wrap: anywhere; }}
        .roster-table .ptopic {{ max-width: 160px; }}
        .roster-table .pscore {{ font: 700 0.95rem var(--font-mono); color: var(--guesser); text-align: right; }}
        .roster-table .pact {{ white-space: nowrap; text-align: right; }}
        .roster-table .role-select {{ width: auto; min-height: 32px; }}
        .acct-tag {{ color: var(--muted); }}
        .account-row.reset-requested {{ outline: 2px solid #d9a441; background: rgba(217,164,65,0.12); }}
        .reset-note {{ color: #d9a441; font-size: 0.75rem; font-weight: 800; text-transform: uppercase; margin-left: 6px; }}
        #new-topics-dialog::backdrop {{ background: rgba(0,0,0,0.6); }}
        .muted {{ color: var(--muted); }}
        .link-btn {{ background: none; border: 0; padding: 2px 0; color: var(--paper-2); font: inherit; font-size: 0.82rem; cursor: pointer; text-align: left; display: inline-flex; align-items: center; gap: 4px; }}
        .link-btn:hover {{ color: var(--text); text-decoration: underline; }}
        .icon-btn {{ min-width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center; border-radius: 6px; border: 1px solid var(--line); background: var(--ink-3); color: var(--text); font: 600 0.8rem var(--font-ui); cursor: pointer; }}
        .icon-btn:hover {{ border-color: var(--paper-2); }}
        .icon-btn.danger {{ color: var(--liar); border-color: rgba(224,103,90, 0.4); }}
        @media (max-width: 600px) {{
            .roster-table .ptopic, .roster-table th:nth-child(3) {{ display: none; }}
            .roster-table td, .roster-table th {{ padding: 6px 3px; }}
            .roster-table .role-select {{ max-width: 118px; font-size: 0.74rem; padding: 4px 4px; }}
            .roster-table {{ table-layout: fixed; }}
            .roster-table th:nth-child(1) {{ width: 28%; }} .roster-table th:nth-child(4) {{ width: 34px; }} .roster-table th:nth-child(5) {{ width: 78px; }}
        }}
        .player-score {{
            font-size: 0.85rem;
            color: #d9a441;
            font-weight: 700;
            background: rgba(217,164,65, 0.1);
            padding: 3px 8px;
            border-radius: 6px;
        }}

        .logs-console {{
            background: #0e0d0c;
            border: 1px solid #201d1a;
            border-radius: 8px;
            padding: 12px;
            height: 220px;
            overflow-y: auto;
            font-family: var(--font-mono);
            font-size: 0.78rem;
            line-height: 1.5;
        }}
        .log-entry {{ margin-bottom: 5px; display: flex; gap: 8px; align-items: baseline; }}
        .log-time {{ color: #8a8276; font-weight: 600; white-space: nowrap; }}
        .log-badge {{ font-weight: 700; padding: 1px 6px; border-radius: 4px; font-size: 0.7rem; white-space: nowrap; }}
        .log-action {{ color: #d8d0bd; background: rgba(233,228,216, 0.15); border: 1px solid rgba(233,228,216, 0.3); }}
        .log-info {{ color: #c9bfa8; background: rgba(201,191,168, 0.15); border: 1px solid rgba(201,191,168, 0.3); }}
        .log-warn {{ color: #e47f73; background: rgba(224,103,90, 0.15); border: 1px solid rgba(224,103,90, 0.3); font-weight: bold; }}
        .log-msg {{ color: #e2dccf; word-break: break-word; }}

        .reveal-box {{
            background: rgba(94,166,126, 0.2);
            border: 2px solid var(--truth-color);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            margin-bottom: 20px;
        }}

        input[type="text"] {{
            background: #171513;
            border: 1px solid var(--border);
            color: var(--text);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 0.85rem;
            outline: none;
        }}
        input[type="text"]:focus {{
            border-color: var(--primary);
        }}

        .role-multi-select {{
            width: 100%;
            background: #171513;
            color: #f1ece2;
            border: 1px solid #3a352e;
            padding: 6px 8px;
            border-radius: 8px;
            font-size: 0.88rem;
            font-weight: 600;
            cursor: pointer;
            outline: none;
            min-height: 110px;
        }}
        .role-multi-select:focus {{
            border-color: var(--primary);
            box-shadow: 0 0 0 2px rgba(233,228,216, 0.25);
        }}
        .role-multi-select option {{
            padding: 6px 10px;
            margin: 2px 0;
            border-radius: 4px;
            font-size: 0.88rem;
        }}
        .role-multi-select option:checked {{
            background: #c4bba6 !important;
            color: var(--paper-ink) !important;
            font-weight: 700;
        }}


    </style>
</head>
<body class="theme-noir">

    <header class="header">
        <div class="header-left">
            <div class="badge-logo">NOT LYING</div>
            <div class="title-group">
                <h1>Admin Console</h1>
                <p>One of These People Is Not Lying &bull; Port {port}</p>
            </div>
        </div>
        <div class="header-actions">
            <span class="badge badge-live"><span class="dot-pulse"></span> Server Active</span>
            <a href="/admin/control" target="_blank" class="btn btn-sm" style="background: rgba(94,166,126, 0.2); border: 1px solid #5ea67e; color: #9fd2b3;">Stage Controller (No Spoilers)</a>
            <a href="/qr" target="_blank" class="btn btn-qr btn-sm">Open Lobby QR Tab</a>
            <a href="/display" target="_blank" class="btn btn-sm">Public Display &#8599;</a>
            <button class="btn btn-warning btn-sm" onclick="terminateToLobby()" title="Book the winner (most points) and start a fresh lobby">End Game</button>
            <button class="btn btn-danger btn-sm" onclick="resetGame()" title="Zero everyone's scores and roles and sign out temporary players. Unlike End Game, nobody gets a win.">Reset Scores</button>
            <form method="post" action="/api/admin/logout" style="margin:0"><button class="btn btn-sm" type="submit">Log out</button></form>
        </div>
    </header>

    <dialog id="new-topics-dialog" class="card" style="margin: auto; max-width: 420px; color: #ece7dc; border: 1px solid rgba(233,228,216,0.35);">
        <form method="dialog">
            <p style="font-weight: 800; font-size: 1.05rem; margin-bottom: 8px;">Deal new topics to everyone?</p>
            <p style="color: #a39b8c; font-size: 0.88rem; margin-bottom: 14px;">Roles stay the same. Should the current topics count as heard, so these players never get them again?</p>
            <div style="display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end;">
                <button class="btn btn-sm" value="cancel">Cancel</button>
                <button class="btn btn-sm" value="skip" onclick="api('new_topics', {{ record_old: false }})">Don't add to histories</button>
                <button class="btn btn-sm btn-primary" value="add" onclick="api('new_topics', {{ record_old: true }})">Add to histories</button>
            </div>
        </form>
    </dialog>

    <!-- Phase Stepper -->
    <div class="stepper">
        <div class="step" id="step-lobby" onclick="setPhase('lobby')">1. Lobby</div>
        <div class="step" id="step-setup" onclick="setPhase('setup')">2. Setup & Secrets</div>
        <div class="step" id="step-questioning" onclick="setPhase('questioning')">3. Questioning (Untimed)</div>
        <div class="step" id="step-voting" onclick="setPhase('voting')">4. Guesser Accusation</div>
        <div class="step" id="step-reveal" onclick="setPhase('reveal')">5. Truth Reveal</div>
    </div>

    <!-- Quick Phase Action Banner -->
    <div id="phase-action-banner" style="margin-bottom: 20px;"></div>

    <!-- Reveal Banner -->
    <div id="reveal-banner" style="display: none;" class="reveal-box">
        <h2 style="font-size: 1.8rem; margin-bottom: 8px;">THE TRUTH IS REVEALED!</h2>
        <p style="font-size: 1.1rem; color: #e9e4d8; margin-bottom: 12px;">The ONLY person telling the truth this round was:</p>
        <div id="reveal-winner-name" style="font-size: 2.2rem; font-weight: 900; color: var(--truth-color);">---</div>
        <div id="reveal-winner-topic" style="font-size: 1rem; color: #e2d6b8; margin-top: 6px;"></div>
        <div style="margin-top: 16px; display: flex; gap: 14px; justify-content: center; flex-wrap: wrap;">
            <button class="btn btn-primary" onclick="nextRound()" style="font-size: 1.05rem; padding: 12px 24px; font-weight: 800; ">Start New Round <svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-chevron-right"/></svg></button>
            <button class="btn btn-danger" onclick="terminateToLobby()" style="font-size: 1.05rem; padding: 12px 24px; font-weight: 800; ">End Game &amp; Return to Lobby</button>
        </div>
    </div>

    <!-- Dedicated Role Assignment & Topic Control Panel -->
    <div class="card" style="margin-bottom: 24px; background: rgba(32,29,26, 0.85); border: 1px solid rgba(233,228,216, 0.35); box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
            <div>
                <div style="font-size: 1.15rem; font-weight: 800; color: #ece7dc; display: flex; align-items: center; gap: 8px;">
                    <span>Roles</span>
                </div>
                <div style="font-size: 0.82rem; color: #a39b8c; margin-top: 3px;">
                    Configure number of Guessers and Truth Tellers for larger parties. Choose the Lead Voter below.
                </div>
            </div>
        </div>

        <!-- Role Counts Configuration for Larger Parties -->
        <div style="background: rgba(14,13,12, 0.6); padding: 14px 16px; border-radius: 10px; border-1px solid #201d1a; margin-bottom: 16px; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 16px;">
            <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 20px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <label style="font-size: 0.85rem; font-weight: 700; color: #d9a441; display: flex; align-items: center; gap: 6px;">
                        <span>Guessers:</span>
                    </label>
                    <input type="number" id="admin-guesser-count" min="1" max="20" value="1" oninput="updateRoleCounts()" onchange="updateRoleCounts()" style="width: 65px; background: #171513; border: 1px solid #3a352e; color: var(--text); padding: 6px 10px; border-radius: 6px; font-size: 0.95rem; font-weight: 700; text-align: center;">
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <label style="font-size: 0.85rem; font-weight: 700; color: #7cc19a; display: flex; align-items: center; gap: 6px;">
                        <span>Truth Tellers:</span>
                    </label>
                    <input type="number" id="admin-truth-count" min="1" max="20" value="1" oninput="updateRoleCounts()" onchange="updateRoleCounts()" style="width: 65px; background: #171513; border: 1px solid #3a352e; color: var(--text); padding: 6px 10px; border-radius: 6px; font-size: 0.95rem; font-weight: 700; text-align: center;">
                </div>
                <fieldset class="tri" id="role-mode">
                    <legend>Role mix</legend>
                    <input type="radio" name="role-mode" id="rm-one_liar" value="one_liar" onchange="setRoleMode(this.value)"><label for="rm-one_liar" title="Everyone but the guessers and one liar tells the truth">1 Liar</label>
                    <input type="radio" name="role-mode" id="rm-custom" value="custom" onchange="setRoleMode(this.value)" checked><label for="rm-custom" title="Use the Truth Tellers count">Custom</label>
                    <input type="radio" name="role-mode" id="rm-one_truth" value="one_truth" onchange="setRoleMode(this.value)"><label for="rm-one_truth" title="One truth teller, everyone else lies">1 Truth Teller</label>
                </fieldset>
                <label class="pack-item" title="Nobody gets the same role twice in a row, and players who keep missing a role become likelier to get it"><input type="checkbox" id="set-fair_roles" onchange="saveSetting(this)"> <span class="pack-name">Fair role rotation</span></label>
                <fieldset class="tri" id="match-mode" title="Deal topics toward what each player knows (they set interests on their phone)">
                    <legend>Topic matching</legend>
                    <input type="radio" name="match-mode" id="mm-off" value="off" onchange="setMatchMode(this.value)" checked><label for="mm-off" title="Topics are dealt at random">Random</label>
                    <input type="radio" name="match-mode" id="mm-tags" value="tags" onchange="setMatchMode(this.value)"><label for="mm-tags" title="Favor topics sharing a player's chosen tags">Match tags</label>
                    <input type="radio" name="match-mode" id="mm-expertise" value="expertise" onchange="setMatchMode(this.value)"><label for="mm-expertise" title="Favor topics closest to a player's written expertise (local embeddings)">Match expertise</label>
                </fieldset>
                <span class="match-status" id="match-status"></span>
            </div>
            <div id="admin-role-status-badge" style="font-size: 0.82rem; color: #a39b8c;">
                Remaining players are automatically <strong style="color: #e47f73;">Liars</strong>. Exactly <strong style="color: #d9a441;">1 Guesser</strong> votes after team consensus!
            </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px;">
            <!-- Dedicated Guesser Dropdown Container -->
            <div id="admin-guesser-card" style="background: rgba(0, 0, 0, 0.35); padding: 14px 16px; border-radius: 10px; border-left: 4px solid var(--guesser-color); border: 1px solid #2a2622; border-left-width: 4px;">
                <label style="font-size: 0.82rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; color: var(--guesser-color); display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                    <span id="admin-guesser-label-title">Lead Guesser (Designated Voter)</span>
                    <span class="badge" id="admin-guesser-badge" style="background: rgba(217,164,65, 0.2); color: #d9a441; font-size: 0.7rem;">Only Voter</span>
                </label>
                <div id="admin-guesser-select-holder">
                    <select id="admin-select-guesser" onchange="chooseGuesser(this.value)" style="width: 100%; background: #171513; color: #f1ece2; border: 1px solid #3a352e; padding: 10px 12px; border-radius: 8px; font-size: 0.95rem; font-weight: 600; cursor: pointer;">
                        <option value="">-- Select Guesser --</option>
                    </select>
                </div>
                <!-- Sub-selector for Lead Voter when multiple guessers are configured -->
                <div id="admin-lead-voter-subcard" style="display: none; margin-top: 10px; padding: 8px 10px; background: rgba(217,164,65, 0.1); border: 1px solid rgba(217,164,65, 0.3); border-radius: 8px;">
                    <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                        <span style="font-size: 0.78rem; font-weight: 800; color: #d9a441; text-transform: uppercase;">Lead Voter:</span>
                        <select id="admin-select-lead-voter" onchange="chooseLeadVoter(this.value)" style="flex: 1; background: #171513; color: #f1ece2; border: 1px solid #a8772a; padding: 5px 8px; border-radius: 6px; font-size: 0.82rem; font-weight: 700; cursor: pointer;">
                        </select>
                    </div>
                </div>
                <div id="admin-guesser-help" style="font-size: 0.75rem; color: #ead29c; margin-top: 6px;">
                    The single guesser allowed to cast the vote. Other guessers collaborate to reach consensus.
                </div>
            </div>

            <!-- Dedicated Truth Teller Dropdown Container -->
            <div id="admin-truth-card" style="background: rgba(0, 0, 0, 0.35); padding: 14px 16px; border-radius: 10px; border-left: 4px solid var(--truth-color); border: 1px solid #2a2622; border-left-width: 4px;">
                <label style="font-size: 0.82rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; color: var(--truth-color); display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                    <span id="admin-truth-label-title">Truth Teller</span>
                    <span class="badge" id="admin-truth-badge" style="background: rgba(94,166,126, 0.2); color: #7cc19a; font-size: 0.7rem;">100% Real Facts</span>
                </label>
                <div id="admin-truth-select-holder">
                    <select id="admin-select-truth-teller" onchange="chooseTruthTeller(this.value)" style="width: 100%; background: #171513; color: #f1ece2; border: 1px solid #3a352e; padding: 10px 12px; border-radius: 8px; font-size: 0.95rem; font-weight: 600; cursor: pointer;">
                        <option value="">-- Select Truth Teller --</option>
                    </select>
                </div>
                <div id="admin-truth-help" style="font-size: 0.75rem; color: #9fd2b3; margin-top: 6px;">
                    Receives true statement &amp; full facts description.
                </div>
            </div>
        </div>
    </div>

    <div class="main-grid">
        <!-- Left Column: Dossier & Logs -->
        <div>
            <!-- Secret Dossier -->
            <div class="card dossier">
                <div class="card-header">
                    <div class="card-title dossier-title">ADMIN SECRET DOSSIER</div>
                    <button class="btn btn-sm" onclick="toggleAllTopics()" id="all-topics-btn">Reveal All Topics</button>
                </div>

                <!-- Topic History Status (Separate Truth & Lies) & Reset Button -->
                <div style="background: rgba(0, 0, 0, 0.35); padding: 10px 14px; border-radius: 8px; margin-bottom: 14px; border: 1px solid #2a2622;">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                        <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                            <span style="font-size: 0.84rem; font-weight: 700; color: #d3cbbb; display: flex; align-items: center; gap: 6px;">
                                Topic History:
                            </span>
                            <div style="background: rgba(94,166,126, 0.15); border: 1px solid rgba(94,166,126, 0.4); padding: 3px 10px; border-radius: 6px; font-size: 0.82rem; color: #bfe0cb; font-weight: 600;">
                                Truth: <strong id="used-truth-count" style="color: #7cc19a;">0</strong> / <span id="total-truth-count">500</span> used
                            </div>
                            <div style="background: rgba(224,103,90, 0.15); border: 1px solid rgba(224,103,90, 0.4); padding: 3px 10px; border-radius: 6px; font-size: 0.82rem; color: #eda79e; font-weight: 600;">
                                Lies: <strong id="used-lies-count" style="color: #e47f73;">0</strong> / <span id="total-lies-count">500</span> used
                            </div>
                            <div style="font-size: 0.78rem; color: #a39b8c;">
                                (<span id="used-topics-count">0</span> / <span id="total-topics-count">500</span> topics used)
                            </div>
                        </div>
                        <div style="display: flex; gap: 6px; align-items: center;">
                            <button class="btn btn-sm" id="toggle-topic-drawer-btn" style="background: #201d1a; font-size: 0.75rem; border: 1px solid #36312b;" onclick="toggleTopicHistoryDetails()">View Used</button>
                            <button class="btn btn-sm" style="background: #36312b; font-size: 0.75rem;" onclick="clearTopicHistory()">Reset Global History</button>
                        </div>
                    </div>

                    <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #2a2622;">
                        <div style="font-size: 0.78rem; color: #a39b8c; font-weight: 700; margin-bottom: 6px;">TOPIC PACKS</div>
                        <div id="pack-list" class="pack-list"></div>
                    </div>

                    <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #2a2622;">
                        <div style="font-size: 0.78rem; color: #a39b8c; font-weight: 700; margin-bottom: 6px;">SETTINGS</div>
                        <div class="pack-list">
                            <label class="pack-item" title="Skip topics anyone has heard in past games"><input type="checkbox" id="set-use_global" onchange="saveSetting(this)"> <span class="pack-name">Global history</span></label>
                            <label class="pack-item" title="Skip topics the permanent accounts in this lobby have heard"><input type="checkbox" id="set-use_user" onchange="saveSetting(this)"> <span class="pack-name">Per-player history</span></label>
                            <label class="pack-item" title="Liars also see background facts that ground their lie"><input type="checkbox" id="set-lying_facts" onchange="saveSetting(this)"> <span class="pack-name">Lying Facts</span></label>
                            <label class="pack-item" title="Facts are readable during Briefing, then whited out for questioning and the accusation"><input type="checkbox" id="set-hide_facts" onchange="saveSetting(this)"> <span class="pack-name">Hide facts during questioning</span></label>
                            <label class="pack-item" title="End the game (and book the win) after this long without any activity"><span class="pack-name">End game after</span>
                                <input type="number" id="set-idle_minutes" min="5" max="1440" step="5" style="width: 70px;" onchange="api('set_setting', {{ name: 'idle_minutes', value: +this.value }})"> <span class="pack-name">min idle</span></label>
                        </div>
                        <div style="font-size: 0.75rem; color: #a39b8c; margin-top: 6px;"><span id="blocked-topics-count">0</span> topics blocked for this lobby.</div>
                    </div>

                    <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #2a2622;">
                        <div style="font-size: 0.78rem; color: #a39b8c; font-weight: 700; margin-bottom: 6px;">SAVED ACCOUNTS</div>
                        <div id="account-list" class="account-list"></div>
                    </div>

                    <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #2a2622;">
                        <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                            <span style="font-size: 0.78rem; color: #a39b8c; font-weight: 700;">STATEMENT REVIEWS</span>
                            <span><button class="btn btn-sm" onclick="loadReviews()">Load</button> <a class="btn btn-sm" href="/api/reviews" target="_blank">Raw JSON &#8599;</a></span>
                        </div>
                        <div id="review-list" class="account-list"></div>
                    </div>

                    <!-- Collapsible Drawer for viewing used statements archive -->
                    <div id="topic-history-drawer" style="display: none; margin-top: 12px; padding-top: 12px; border-top: 1px solid #2a2622;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <div style="font-size: 0.78rem; color: #a39b8c; font-weight: 700;">HISTORY ARCHIVE (ALL ROUNDS)</div>
                            <button class="btn btn-sm" id="toggle-drawer-mask-btn" style="background: #201d1a; font-size: 0.72rem; padding: 2px 8px;" onclick="toggleDrawerMask()">Hide Details</button>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                            <div style="background: rgba(94,166,126, 0.06); border: 1px solid rgba(94,166,126, 0.2); border-radius: 6px; padding: 8px;">
                                <div style="font-size: 0.78rem; font-weight: 700; color: #7cc19a; margin-bottom: 6px;">
                                    True Statements Used (<span id="drawer-truth-count">0</span>)
                                </div>
                                <div id="drawer-truth-list" style="max-height: 220px; overflow-y: auto; font-size: 0.78rem; color: #d3cbbb; display: flex; flex-direction: column; gap: 6px;"></div>
                            </div>
                            <div style="background: rgba(224,103,90, 0.06); border: 1px solid rgba(224,103,90, 0.2); border-radius: 6px; padding: 8px;">
                                <div style="font-size: 0.78rem; font-weight: 700; color: #e47f73; margin-bottom: 6px;">
                                    False Statements Used (<span id="drawer-lies-count">0</span>)
                                </div>
                                <div id="drawer-lies-list" style="max-height: 220px; overflow-y: auto; font-size: 0.78rem; color: #d3cbbb; display: flex; flex-direction: column; gap: 6px;"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Guesser banner -->
                <div class="guesser-banner">
                    <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; color: var(--text-muted); font-weight: 700;">
                        The Guesser Team (1 Voter &bull; Others Deliberate):
                    </div>
                    <div class="guesser-name" id="dossier-guesser-name">---</div>
                    <div id="dossier-other-guessers" style="font-size: 0.85rem; color: #efdcaa; margin-top: 4px;"></div>
                    <div style="font-size: 0.8rem; color: #ead29c; margin-top: 4px;">
                        • Only the designated Lead Voter can cast the accusation.<br>
                        • Other guessers deliberate with the voter to reach consensus.<br>
                        • <strong>Guessers receive NO topics or clues</strong>.
                    </div>
                </div>

                <!-- Truth teller banner -->
                <div class="truth-banner">
                    <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; color: var(--text-muted); font-weight: 700;">
                        True Statements Used (Current Round):
                    </div>
                    <div class="truth-person-name" id="dossier-truth-name">---</div>
                    <div id="dossier-truth-content" style="margin-top: 8px;"></div>
                </div>

                <!-- Liars list with their individual topics -->
                <div style="margin-top: 14px;">
                    <div style="font-size: 0.85rem; font-weight: 700; color: var(--liar-color); margin-bottom: 8px; text-transform: uppercase;">
                        False Statements Used (Current Round):
                    </div>
                    <div id="dossier-liars-container"></div>
                </div>

                <div style="margin-top: 16px; display: flex; gap: 8px; flex-wrap: wrap;">
                    <button class="btn btn-sm btn-primary" onclick="randomizeRoles()">Randomize Roles</button>
                    <button class="btn btn-sm btn-primary" onclick="newTopics()">New Topics</button>
                    <button class="btn btn-sm btn-warning" onclick="revealTruth()">Reveal Truth Now</button>
                </div>
            </div>



            <!-- Logs -->
            <div class="card" id="logs-card">
                <div class="card-header">
                    <div class="card-title" style="display: flex; align-items: center; gap: 8px;">
                        <span>Live Terminal & Server Logs</span>
                        <span id="logs-count" style="font-size: 0.72rem; background: #201d1a; color: #a39b8c; padding: 2px 8px; border-radius: 10px; font-weight: 600;">0 events</span>
                    </div>
                    <div style="display: flex; gap: 6px;">
                        <button class="btn btn-sm" onclick="api('clear_logs')" style="background: #201d1a; font-size: 0.75rem; border: 1px solid #36312b;">Clear</button>
                        <button class="btn btn-sm" onclick="fetchState()" style="font-size: 0.75rem;">Refresh</button>
                    </div>
                </div>
                <div class="logs-console" id="logs-list">
                    <div style="color: #8a8276; font-style: italic; padding: 4px;">Connecting to server event stream...</div>
                </div>
            </div>
        </div>

        <!-- Right Column: Roster & Accusation -->
        <div>
            <!-- QR Banner Card -->
            <div class="card" style="background: rgba(233,228,216, 0.15); border: 1px solid rgba(233,228,216, 0.4);">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div>
                        <div style="font-weight: 700; font-size: 0.95rem;">Players Join via Phone</div>
                        <div style="font-size: 0.8rem; color: #e9e4d8; word-break: break-all;">{join_url}</div>
                    </div>
                </div>
            </div>

            <!-- Players Roster with direct role selection -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Players Roster (<span id="player-count">0</span>)</div>
                </div>

                <div style="display: flex; gap: 8px; margin-bottom: 14px;">
                    <input type="text" id="new-player-name" placeholder="Add player manually..." style="flex: 1;" onkeypress="if(event.key==='Enter')addPlayer()">
                    <button class="btn btn-sm btn-primary" onclick="addPlayer()">+ Add</button>
                </div>

                <div id="players-list"></div>
            </div>

            <!-- Guesser Accusation Box -->
            <div class="card" style="border: 1px solid #d9a441;">
                <div class="card-header">
                    <div class="card-title" style="color: #d9a441;">Guesser's Accusation</div>
                    <span class="badge" style="background: rgba(217,164,65, 0.2); color: #d9a441;">Decisive Vote</span>
                </div>
                <p style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 10px;">
                    Only the Guesser (<strong id="guesser-vote-name">Guesser</strong>) is allowed to cast a vote!
                </p>
                <div id="guesser-voting-box"></div>
            </div>
        </div>
    </div>

    <script>
        let gameState = {{}};
        let revealedTopics = {{}};
        let showAllTopics = false;

        function toggleTopic(id) {{
            revealedTopics[id] = !revealedTopics[id];
            render(gameState);
        }}

        function toggleAllTopics() {{
            showAllTopics = !showAllTopics;
            revealedTopics['tt'] = showAllTopics;
            if (gameState && gameState.players) {{
                gameState.players.forEach(p => {{
                    revealedTopics[p.id] = showAllTopics;
                }});
            }}
            const btn = document.getElementById("all-topics-btn");
            if (btn) btn.innerText = showAllTopics ? "Hide All Topics" : "Reveal All Topics";
            render(gameState);
        }}

        async function api(action, payload = {{}}) {{
            try {{
                const res = await fetch("/api/action", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ action, ...payload }})
                }});
                if (res.status === 401) {{ location.href = "/admin/login"; return null; }}
                const data = await res.json();
                if (!res.ok) {{
                    if (data && data.error) {{
                        alert(data.error);
                    }}
                    return null;
                }}
                render(data);
                return data;
            }} catch (err) {{
                console.error("API error:", err);
            }}
        }}

        async function fetchState() {{
            try {{
                const res = await fetch("/api/state?role=admin&_t=" + Date.now(), {{ cache: "no-store" }});
                if (res.status === 401) {{ location.href = "/admin/login"; return; }}
                const data = await res.json();
                render(data);
            }} catch (err) {{
                console.error("Fetch error:", err);
            }}
        }}

        function chooseGuesser(playerId) {{
            if (playerId) api("set_guesser", {{ player_id: playerId }});
        }}

        function chooseTruthTeller(playerId) {{
            if (playerId) api("set_truth_teller", {{ player_id: playerId }});
        }}

        function setPlayerRoleDirect(playerId, newRole) {{
            api("set_role", {{ player_id: playerId, role: newRole }});
        }}

        function render(state) {{
            if (!state) return;
            gameState = state;

            const phases = ["lobby", "setup", "questioning", "voting", "reveal"];
            const isReveal = (state.phase === "reveal");
            phases.forEach(p => {{
                const el = document.getElementById("step-" + p);
                if (el) {{
                    el.classList.toggle("active", state.phase === p);
                    if (["setup", "questioning", "voting"].includes(p)) {{
                        el.style.opacity = isReveal ? "0.35" : "1";
                        el.style.cursor = isReveal ? "not-allowed" : "pointer";
                        el.style.pointerEvents = isReveal ? "none" : "auto";
                    }}
                }}
            }});

            const banner = document.getElementById("phase-action-banner");
            const req = state.role_requirements;
            const roleBadge = document.getElementById("admin-role-status-badge");
            if (roleBadge && req) {{
                if (req.valid) {{
                    roleBadge.innerHTML = `<span style="color: #7cc19a; font-weight: 700;">Valid Setup:</span> ${{req.guessers}} Guesser(s) &bull; ${{req.truth_tellers}} Truth Teller(s) &bull; ${{req.liars}} Liar(s) (${{req.players}} players total)`;
                }} else {{
                    roleBadge.innerHTML = `<span style="color: #e47f73; font-weight: 700;">${{escapeHtml(req.error)}}</span>`;
                }}
            }}

            if (banner) {{
                let bannerHtml = "";
                if (state.phase === "lobby") {{
                    const isReqValid = !req || req.valid;
                    const reqMsg = req ? req.error : null;
                    bannerHtml = `
                        <div style="background: rgba(233,228,216, 0.25); border: 2px solid ${{isReqValid ? '#e9e4d8' : '#c99236'}}; border-radius: 12px; padding: 16px 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; box-shadow: 0 4px 16px rgba(233,228,216, 0.2);">
                            <div style="max-width: 650px;">
                                <div style="font-size: 1.15rem; font-weight: 800; color: #ece7dc;">Lobby Phase Active</div>
                                <div style="font-size: 0.85rem; color: #e9e4d8; margin-top: 2px;">
                                    Players are joining via phone. Once ready, begin the round to reveal secret topics & statements!
                                </div>
                                ${{isReqValid ? `<div style="margin-top: 6px; font-size: 0.8rem; color: #d9a441; font-weight: 700;">${{(state.ready_ids || []).length}}/${{(state.players || []).length}} ready on their phones</div>` : ""}}
                                ${{!isReqValid ? `
                                    <div style="margin-top: 8px; padding: 8px 12px; background: rgba(224,103,90, 0.2); border: 1px solid #e0675a; border-radius: 6px; font-size: 0.82rem; color: #eda79e; font-weight: 700;">
                                        ${{escapeHtml(reqMsg || 'Cannot start: at least 1 Guesser, 1 Truth Teller, and 1 Liar must be present.')}}
                                    </div>
                                ` : `
                                    <div style="margin-top: 6px; font-size: 0.8rem; color: #7cc19a; font-weight: 600;">
                                        Ready to start: ${{req ? req.guessers : 1}} Guesser, ${{req ? req.truth_tellers : 1}} Truth Teller, ${{req ? req.liars : 1}} Liar (${{req ? req.players : 3}} players)
                                    </div>
                                `}}
                            </div>
                            <button class="btn btn-primary" onclick="startRoundFromLobby()" style="font-size: 1.05rem; padding: 12px 24px; font-weight: 800; background: ${{isReqValid ? 'var(--paper)' : 'var(--ink-3)'}}; color: ${{isReqValid ? 'var(--paper-ink)' : 'var(--muted)'}}; cursor: ${{isReqValid ? 'pointer' : 'not-allowed'}};">
                                <svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-play"/></svg> Start Round (Move to Setup & Secrets)
                            </button>
                        </div>
                    `;
                }} else if (state.phase === "setup") {{
                    bannerHtml = `
                        <div style="background: rgba(94,166,126, 0.2); border: 2px solid #5ea67e; border-radius: 12px; padding: 16px 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
                            <div>
                                <div style="font-size: 1.15rem; font-weight: 800; color: #ece7dc;">Setup & Secrets Active</div>
                                <div style="font-size: 0.85rem; color: #dcefe2; margin-top: 2px;">
                                    Topics & clues are live on player phones! When everyone has reviewed their cards, proceed to Questioning.
                                </div>
                            </div>
                            <button class="btn btn-primary" onclick="setPhase('questioning')" style="font-size: 1.05rem; padding: 12px 24px; font-weight: 800; ">
                                <svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-play"/></svg> Begin Questioning Phase <svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-chevron-right"/></svg>
                            </button>
                        </div>
                    `;
                }} else if (state.phase === "questioning") {{
                    bannerHtml = `
                        <div style="background: rgba(217,164,65, 0.2); border: 2px solid #c99236; border-radius: 12px; padding: 16px 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
                            <div>
                                <div style="font-size: 1.15rem; font-weight: 800; color: #ece7dc;">Questioning Phase (Untimed)</div>
                                <div style="font-size: 0.85rem; color: #f3e6c4; margin-top: 2px;">
                                    The Guesser is interrogating suspects. When questioning ends, advance to Accusation.
                                </div>
                            </div>
                            <button class="btn btn-warning" onclick="setPhase('voting')" style="font-size: 1.05rem; padding: 12px 24px; font-weight: 800; ">
                                <svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-play"/></svg> Advance to Accusation <svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-chevron-right"/></svg>
                            </button>
                        </div>
                    `;
                }} else if (state.phase === "voting") {{
                    bannerHtml = `
                        <div style="background: rgba(224,103,90, 0.2); border: 2px solid #e0675a; border-radius: 12px; padding: 16px 20px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
                            <div>
                                <div style="font-size: 1.15rem; font-weight: 800; color: #ece7dc;">Guesser Accusation Phase</div>
                                <div style="font-size: 0.85rem; color: #f4dcd7; margin-top: 2px;">
                                    Waiting for the Guesser to cast their decisive vote. Once submitted, reveal the truth!
                                </div>
                            </div>
                            <button class="btn btn-danger" onclick="revealTruth()" style="font-size: 1.05rem; padding: 12px 24px; font-weight: 800; ">
                                Reveal Truth Now <svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-chevron-right"/></svg>
                            </button>
                        </div>
                    `;
                }} else {{
                    bannerHtml = "";
                }}
                if (banner.dataset.html !== bannerHtml) {{ banner.innerHTML = bannerHtml; banner.dataset.html = bannerHtml; }}
            }}

            const revealBanner = document.getElementById("reveal-banner");
            if (state.phase === "reveal") {{
                revealBanner.style.display = "block";
                const res = state.last_results || {{}};
                const tt = res.truth_teller || {{}};
                const tts = (res.truth_tellers && res.truth_tellers.length > 0) ? res.truth_tellers : (tt.name ? [tt] : []);
                const guesser = res.guesser || {{}};
                const pickedList = (res.picked_players && res.picked_players.length > 0) ? res.picked_players : (res.picked_player ? [res.picked_player] : []);
                const isCorrect = res.is_correct;
                const pickedNames = pickedList.map(p => escapeHtml(p.name)).join(" &amp; ") || "Nobody";
                const ttNames = tts.map(t => escapeHtml(t.name)).join(" &amp; ") || "Truth Teller";

                let scoreInfo = "";
                if (isCorrect) {{
                    if (tts.length > 1) {{
                        scoreInfo = `<strong>Correct Accusation!</strong> Guesser team identified all ${{tts.length}} Truth Tellers: <strong>${{pickedNames}}</strong> (+1 pt to Guessers, +1 pt to each Truth Teller)!`;
                    }} else {{
                        scoreInfo = `<strong>Correct Accusation!</strong> Guesser ${{escapeHtml(guesser.name || '')}} found Truth Teller <strong>${{pickedNames}}</strong> (+1 pt each)!`;
                    }}
                }} else if (pickedList.length > 0) {{
                    scoreInfo = `<strong>Bluff Succeeded!</strong> Guesser team accused <strong>${{pickedNames}}</strong> (+1 pt awarded to each accused player). The actual Truth Teller(s) was/were <strong>${{ttNames}}</strong>!`;
                }} else {{
                    scoreInfo = `Round ended without an accusation. The actual Truth Teller(s) was/were <strong>${{ttNames}}</strong>.`;
                }}

                let standingsTable = (state.standings || []).map((s, idx) => {{
                    let medal = `${{idx + 1}}.`;
                    let gained = s.pts_gained > 0 ? `<span class="badge" style="background: rgba(94,166,126, 0.25); color: #7cc19a; font-weight: 700;">+${{s.pts_gained}} pt</span>` : `<span style="color: #8a8276;">+0</span>`;
                    return `
                        <tr style="border-bottom: 1px solid rgba(255,255,255,0.08);">
                            <td style="padding: 6px 10px; text-align: center; font-weight: 800;">${{medal}}</td>
                            <td style="padding: 6px 10px; font-weight: 700; color: #ece7dc;">${{escapeHtml(s.name)}}</td>
                            <td style="padding: 6px 10px; text-align: center;">${{gained}}</td>
                            <td style="padding: 6px 10px; font-weight: 900; color: #d9a441; text-align: right;">${{s.score}} pts</td>
                        </tr>
                    `;
                }}).join("");

                let ttsDetails = tts.map(t => `
                    <div style="background: rgba(0,0,0,0.3); border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; text-align: left; max-width: 650px; margin-left: auto; margin-right: auto; border-left: 3px solid #5ea67e;">
                        <div style="font-size: 0.8rem; font-weight: 800; color: #9fd2b3; text-transform: uppercase;">
                            Truth Teller: ${{escapeHtml(t.name || '')}} (${{escapeHtml(t.topic || '')}})
                        </div>
                        <div style="font-size: 0.9rem; color: #e2dccf; margin-top: 2px;">${{escapeHtml(t.true_statement || '')}}</div>
                    </div>
                `).join("");

                const revealHtml = `
                    <h2 style="font-size: 1.8rem; margin-bottom: 6px; color: ${{isCorrect ? '#7cc19a' : '#d9a441'}};">
                        ${{isCorrect ? 'CORRECT ACCUSATION!' : 'BLUFF SUCCESSFUL!'}}
                    </h2>
                    <div style="font-size: 1.05rem; color: #ece7dc; margin-bottom: 10px;">${{scoreInfo}}</div>
                    ${{ttsDetails}}

                    <div style="max-width: 500px; margin: 0 auto 16px auto; background: rgba(0,0,0,0.4); border-radius: 10px; padding: 12px; border: 1px solid #2a2622;">
                        <div style="font-size: 0.9rem; font-weight: 800; color: #d9a441; margin-bottom: 8px; text-transform: uppercase;">
                            Current Standings (Round ${{state.round}})
                        </div>
                        <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
                            <thead>
                                <tr style="color: #a39b8c; font-size: 0.72rem; text-transform: uppercase;">
                                    <th style="padding: 4px 10px; text-align: center;">Rank</th>
                                    <th style="padding: 4px 10px; text-align: left;">Player</th>
                                    <th style="padding: 4px 10px; text-align: center;">Round</th>
                                    <th style="padding: 4px 10px; text-align: right;">Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${{standingsTable}}
                            </tbody>
                        </table>
                    </div>

                    <div style="display: flex; align-items: center; gap: 14px;">
                        <span style="font-size: 0.85rem; color: #d9a441; font-weight: 700;">${{(state.ready_ids || []).length}}/${{(state.players || []).length}} ready</span>
                        <button class="btn btn-primary" onclick="nextRound()" style="font-size: 1rem; padding: 10px 24px; font-weight: 800;">
                            Next Round <svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-chevron-right"/></svg>
                        </button>
                    </div>
                `;
                if (revealBanner.dataset.html !== revealHtml) {{ revealBanner.innerHTML = revealHtml; revealBanner.dataset.html = revealHtml; }}
            }} else {{
                revealBanner.style.display = "none";
            }}

            // Update Role Count inputs if not currently being edited
            const gCountInput = document.getElementById("admin-guesser-count");
            const ttCountInput = document.getElementById("admin-truth-count");
            if (gCountInput && document.activeElement !== gCountInput) {{
                gCountInput.value = state.target_guesser_count || 1;
            }}
            const roleMode = state.role_mode || "custom";
            const modeRadio = document.getElementById("rm-" + roleMode);
            if (modeRadio && !modeRadio.checked) modeRadio.checked = true;
            if (ttCountInput) {{
                ttCountInput.disabled = roleMode !== "custom";
                ttCountInput.parentElement.classList.toggle("role-count-off", roleMode !== "custom");
                if (document.activeElement !== ttCountInput) {{
                    ttCountInput.value = roleMode === "custom" ? (state.target_truth_teller_count || 1) : (state.truth_teller_count || 1);
                }}
            }}

            const targetG = state.target_guesser_count || 1;
            const targetTT = state.target_truth_teller_count || 1;
            const isMultiG = targetG > 1;
            const isMultiTT = targetTT > 1;

            // Populate Dedicated Guesser Dropdown (Multi-select if target > 1)
            const gSelectHolder = document.getElementById("admin-guesser-select-holder");
            const gTitle = document.getElementById("admin-guesser-label-title");
            const gBadge = document.getElementById("admin-guesser-badge");
            const gHelp = document.getElementById("admin-guesser-help");
            const leadVoterSubcard = document.getElementById("admin-lead-voter-subcard");
            const leadVoterSelect = document.getElementById("admin-select-lead-voter");

            const currentGuessers = (state.players || []).filter(p => p.is_guesser);
            const currentVoterId = state.voting_guesser_id || state.guesser_id;

            if (gSelectHolder) {{
                if (isMultiG) {{
                    if (gTitle) gTitle.innerText = `Guesser Team (Multi-Select)`;
                    if (gBadge) {{
                        gBadge.innerText = `${{currentGuessers.length}} / ${{targetG}} Selected`;
                        gBadge.style.background = (currentGuessers.length === targetG) ? "rgba(94,166,126, 0.2)" : "rgba(217,164,65, 0.2)";
                        gBadge.style.color = (currentGuessers.length === targetG) ? "#7cc19a" : "#d9a441";
                    }}
                    if (gHelp) gHelp.innerHTML = `Click or tap players to select ${{targetG}} Guessers. Selected guessers collaborate to reach consensus.`;
                    
                    if (leadVoterSubcard) leadVoterSubcard.style.display = "block";
                    if (leadVoterSelect && document.activeElement !== leadVoterSelect) {{
                        let lvHtml = `<option value="">-- Choose Lead Voter --</option>`;
                        currentGuessers.forEach(g => {{
                            const sel = (g.id === currentVoterId) ? "selected" : "";
                            lvHtml += `<option value="${{g.id}}" ${{sel}}>${{escapeHtml(g.name)}} (Lead Voter)</option>`;
                        }});
                        leadVoterSelect.innerHTML = lvHtml;
                    }}

                    let gSelect = document.getElementById("admin-select-guesser");
                    const needsRebuild = !gSelect || !gSelect.multiple;
                    if (needsRebuild) {{
                        const size = Math.min(6, Math.max(3, state.players.length));
                        gSelectHolder.innerHTML = `<select id="admin-select-guesser" class="role-multi-select" multiple size="${{size}}" onchange="onGuesserMultiChange(this)"></select>`;
                        gSelect = document.getElementById("admin-select-guesser");
                        attachToggleBehavior(gSelect, onGuesserMultiChange);
                    }}

                    if (document.activeElement !== gSelect) {{
                        let optionsHtml = "";
                        state.players.forEach(p => {{
                            const isG = p.is_guesser;
                            const isVoter = (p.id === currentVoterId);
                            const roleTag = isVoter ? " (Lead Voter)" : (isG ? " (Consultant)" : "");
                            const prefix = isG ? "[✓] " : "[  ] ";
                            optionsHtml += `<option value="${{p.id}}" ${{isG ? "selected" : ""}}>${{prefix}}${{escapeHtml(p.name)}}${{roleTag}}</option>`;
                        }});
                        gSelect.innerHTML = optionsHtml;
                    }}
                }} else {{
                    if (gTitle) gTitle.innerText = `Lead Guesser (Designated Voter)`;
                    if (gBadge) {{
                        gBadge.innerText = `Only Voter`;
                        gBadge.style.background = "rgba(217,164,65, 0.2)";
                        gBadge.style.color = "#d9a441";
                    }}
                    if (gHelp) gHelp.innerText = `The single guesser allowed to cast the vote. Other guessers collaborate to reach consensus.`;
                    if (leadVoterSubcard) leadVoterSubcard.style.display = "none";

                    let gSelect = document.getElementById("admin-select-guesser");
                    const needsRebuild = !gSelect || gSelect.multiple;
                    if (needsRebuild) {{
                        gSelectHolder.innerHTML = `<select id="admin-select-guesser" onchange="chooseGuesser(this.value)" style="width: 100%; background: #171513; color: #f1ece2; border: 1px solid #3a352e; padding: 10px 12px; border-radius: 8px; font-size: 0.95rem; font-weight: 600; cursor: pointer;"></select>`;
                        gSelect = document.getElementById("admin-select-guesser");
                    }}

                    if (document.activeElement !== gSelect) {{
                        let gHtml = `<option value="">-- Select Guesser --</option>`;
                        state.players.forEach(p => {{
                            const sel = (p.id === currentVoterId) ? "selected" : "";
                            gHtml += `<option value="${{p.id}}" ${{sel}}>${{escapeHtml(p.name)}}${{p.is_guesser ? ' (Guesser)' : ''}}</option>`;
                        }});
                        gSelect.innerHTML = gHtml;
                    }}
                }}
            }}

            // Populate Dedicated Truth Teller Dropdown (Multi-select if target > 1)
            const ttSelectHolder = document.getElementById("admin-truth-select-holder");
            const ttTitle = document.getElementById("admin-truth-label-title");
            const ttBadge = document.getElementById("admin-truth-badge");
            const ttHelp = document.getElementById("admin-truth-help");

            const currentTTs = (state.players || []).filter(p => p.is_truth_teller);
            const currentTTIds = state.truth_teller_ids || (state.truth_teller_id ? [state.truth_teller_id] : []);

            if (ttSelectHolder) {{
                if (isMultiTT) {{
                    if (ttTitle) ttTitle.innerText = `Truth Tellers (Multi-Select)`;
                    if (ttBadge) {{
                        ttBadge.innerText = `${{currentTTs.length}} / ${{targetTT}} Selected`;
                        ttBadge.style.background = (currentTTs.length === targetTT) ? "rgba(94,166,126, 0.2)" : "rgba(217,164,65, 0.2)";
                        ttBadge.style.color = (currentTTs.length === targetTT) ? "#7cc19a" : "#d9a441";
                    }}
                    if (ttHelp) ttHelp.innerHTML = `Click or tap players to select ${{targetTT}} Truth Tellers. Each receives unique verified facts.`;

                    let ttSelect = document.getElementById("admin-select-truth-teller");
                    const needsRebuild = !ttSelect || !ttSelect.multiple;
                    if (needsRebuild) {{
                        const size = Math.min(6, Math.max(3, state.players.length));
                        ttSelectHolder.innerHTML = `<select id="admin-select-truth-teller" class="role-multi-select" multiple size="${{size}}" onchange="onTruthTellerMultiChange(this)"></select>`;
                        ttSelect = document.getElementById("admin-select-truth-teller");
                        attachToggleBehavior(ttSelect, onTruthTellerMultiChange);
                    }}

                    if (document.activeElement !== ttSelect) {{
                        let optionsHtml = "";
                        state.players.forEach(p => {{
                            if (!p.is_guesser) {{
                                const isTT = currentTTIds.includes(p.id) || p.is_truth_teller;
                                const prefix = isTT ? "[✓] " : "[  ] ";
                                optionsHtml += `<option value="${{p.id}}" ${{isTT ? "selected" : ""}}>${{prefix}}${{escapeHtml(p.name)}}</option>`;
                            }}
                        }});
                        ttSelect.innerHTML = optionsHtml;
                    }}
                }} else {{
                    if (ttTitle) ttTitle.innerText = `Truth Teller`;
                    if (ttBadge) {{
                        ttBadge.innerText = `100% Real Facts`;
                        ttBadge.style.background = "rgba(94,166,126, 0.2)";
                        ttBadge.style.color = "#7cc19a";
                    }}
                    if (ttHelp) ttHelp.innerText = `Receives true statement & full facts description.`;

                    let ttSelect = document.getElementById("admin-select-truth-teller");
                    const needsRebuild = !ttSelect || ttSelect.multiple;
                    if (needsRebuild) {{
                        ttSelectHolder.innerHTML = `<select id="admin-select-truth-teller" onchange="chooseTruthTeller(this.value)" style="width: 100%; background: #171513; color: #f1ece2; border: 1px solid #3a352e; padding: 10px 12px; border-radius: 8px; font-size: 0.95rem; font-weight: 600; cursor: pointer;"></select>`;
                        ttSelect = document.getElementById("admin-select-truth-teller");
                    }}

                    if (document.activeElement !== ttSelect) {{
                        let ttHtml = `<option value="">-- Select Truth Teller --</option>`;
                        state.players.forEach(p => {{
                            if (!p.is_guesser) {{
                                const isTT = (p.id === state.truth_teller_id) || currentTTIds.includes(p.id);
                                const sel = isTT ? "selected" : "";
                                ttHtml += `<option value="${{p.id}}" ${{sel}}>${{escapeHtml(p.name)}}</option>`;
                            }}
                        }});
                        ttSelect.innerHTML = ttHtml;
                    }}
                }}
            }}

            // Topic History Counters (Separate Truth and Lies)
            renderPacks(state.packs || []);
            renderSettings(state);
            if (document.getElementById("used-topics-count")) {{
                document.getElementById("used-topics-count").innerText = state.used_topics_count || 0;
                document.getElementById("total-topics-count").innerText = state.total_topics_count || 500;
            }}
            if (document.getElementById("used-truth-count")) {{
                document.getElementById("used-truth-count").innerText = (state.used_true_count !== undefined ? state.used_true_count : (state.used_truth_count !== undefined ? state.used_truth_count : 0));
                document.getElementById("total-truth-count").innerText = state.total_truth_count || state.total_true_count || 500;
            }}
            if (document.getElementById("used-lies-count")) {{
                document.getElementById("used-lies-count").innerText = (state.used_false_count !== undefined ? state.used_false_count : (state.used_lies_count !== undefined ? state.used_lies_count : 0));
                document.getElementById("total-lies-count").innerText = state.total_lies_count || state.total_false_count || 500;
            }}

            // Dossier: Guesser Team
            const voterName = state.voting_guesser_name || state.guesser_name || "Unassigned";
            document.getElementById("dossier-guesser-name").innerText = `${{voterName}} (Lead Voter)`;
            if (document.getElementById("guesser-vote-name")) {{
                document.getElementById("guesser-vote-name").innerText = voterName;
            }}
            const otherGuessers = (state.players || []).filter(p => p.is_guesser && p.id !== (state.voting_guesser_id || state.guesser_id));
            const otherGBox = document.getElementById("dossier-other-guessers");
            if (otherGBox) {{
                if (otherGuessers.length > 0) {{
                    otherGBox.innerHTML = `<strong>Consulting Guesser(s):</strong> ` + otherGuessers.map(g => escapeHtml(g.name)).join(", ");
                }} else {{
                    otherGBox.innerHTML = "";
                }}
            }}

            // Dossier: Truth Teller(s) (Topic and summary hidden unless button is pressed)
            const tts = (state.players || []).filter(p => p.is_truth_teller);
            const ttBox = document.getElementById("dossier-truth-content");
            if (ttBox) {{
                if (tts.length > 0) {{
                    document.getElementById("dossier-truth-name").innerText = tts.map(t => t.name).join(", ");
                    let ttsHtml = "";
                    tts.forEach((t, idx) => {{
                        const key = 'tt_' + t.id;
                        const isRevealed = !!revealedTopics[key] || !!revealedTopics['tt'];
                        if (isRevealed) {{
                            ttsHtml += `
                                <div style="margin-top: 10px; background: rgba(94,166,126, 0.1); border: 1px solid rgba(94,166,126, 0.4); border-radius: 8px; padding: 10px;">
                                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                                        <span style="font-weight: 800; color: #7cc19a;">${{escapeHtml(t.name)}}</span>
                                        <div>
                                            <span class="badge" style="background: rgba(94,166,126, 0.3); color: #9fd2b3; font-size: 0.85rem; font-weight: 700;">${{escapeHtml(t.topic || "Topic")}}</span>
                                            <button class="btn btn-sm" style="padding: 2px 8px; font-size: 0.75rem; margin-left: 6px;" onclick="toggleTopic('${{key}}')">Hide</button>
                                        </div>
                                    </div>
                                    <div style="margin-top: 6px;">
                                        <div style="font-size: 0.75rem; color: #bfe0cb; font-weight: 700;">TRUE STATEMENT:</div>
                                        <p style="font-size: 0.9rem; margin-top: 3px; color: #ece7dc; line-height: 1.4;">${{escapeHtml(t.statement || "")}}</p>
                                    </div>
                                    <div style="margin-top: 6px;">
                                        <div style="font-size: 0.75rem; color: #9fd2b3; font-weight: 700;">DETAILED DESCRIPTION:</div>
                                        <ul style="font-size: 0.82rem; margin: 3px 0 0; padding-left: 1.1rem; color: #dcefe2; line-height: 1.4;">${{String(t.detailed_description || "").split("\\n").map(l => l.replace(/^\\s*•\\s*/, "").trim()).filter(Boolean).map(l => `<li>${{escapeHtml(l)}}</li>`).join("")}}</ul>
                                    </div>
                                    ${{t.source ? `<div style="font-size: 0.78rem; color: #9fd2b3; margin-top: 6px;">${{srcLinks(t.source)}}</div>` : ""}}
                                </div>
                            `;
                        }} else {{
                            ttsHtml += `
                                <div style="display: flex; align-items: center; justify-content: space-between; background: rgba(0,0,0,0.25); padding: 8px 10px; border-radius: 6px; border: 1px dashed #2a2622; margin-top: 8px;">
                                    <span style="color: #a39b8c; font-size: 0.82rem; font-style: italic;">${{escapeHtml(t.name)}}: Topic &amp; Summary Hidden (Admin Participation Safe)</span>
                                    <button class="btn btn-sm" style="padding: 3px 10px; font-size: 0.75rem;" onclick="toggleTopic('${{key}}')">Show Topic</button>
                                </div>
                            `;
                        }}
                    }});
                    ttBox.innerHTML = ttsHtml;
                }} else {{
                    document.getElementById("dossier-truth-name").innerText = "None assigned";
                    ttBox.innerHTML = '<span style="color: var(--text-muted); font-size: 0.82rem;">Assign a Truth Teller.</span>';
                }}
            }}

            // Dossier: Liars (Each topic and statement hidden unless button is pressed)
            const liarsContainer = document.getElementById("dossier-liars-container");
            liarsContainer.innerHTML = "";
            const liars = state.players.filter(p => !p.is_guesser && !p.is_truth_teller);
            liars.forEach(l => {{
                const card = document.createElement("div");
                card.className = "liar-card";
                const isRevealed = !!revealedTopics[l.id];
                if (isRevealed) {{
                    card.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <span style="font-weight: 700; color: var(--liar-color);">${{escapeHtml(l.name)}}</span>
                            <div>
                                <span class="badge" style="background: rgba(224,103,90, 0.2); color: #eda79e; font-size: 0.8rem; margin-right: 6px;">${{escapeHtml(l.topic || "Topic")}}</span>
                                <button class="btn btn-sm" style="padding: 2px 8px; font-size: 0.72rem;" onclick="toggleTopic('${{l.id}}')">Hide</button>
                            </div>
                        </div>
                        <div style="font-size: 0.72rem; color: #e47f73; font-weight: 700;">FALSE STATEMENT ONLY:</div>
                        <p style="font-size: 0.85rem; color: #e2dccf; margin-top: 2px; line-height: 1.4;">
                            ${{escapeHtml(l.statement || "No statement")}}
                        </p>
                        ${{(l.lie_facts || []).length ? `<ul style="font-size: 0.8rem; color: #c9bfa8; margin: 6px 0 0 18px; line-height: 1.4;">${{l.lie_facts.map(f => `<li>${{escapeHtml(f)}}</li>`).join("")}}</ul>` : ""}}
                    `;
                }} else {{
                    card.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-weight: 700; color: var(--liar-color);">${{escapeHtml(l.name)}}</span>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span style="color: #a39b8c; font-size: 0.8rem; font-style: italic;">Topic Hidden</span>
                                <button class="btn btn-sm" style="padding: 2px 8px; font-size: 0.72rem;" onclick="toggleTopic('${{l.id}}')">Show Topic</button>
                            </div>
                        </div>
                    `;
                }}
                liarsContainer.appendChild(card);
            }});

            // Players Roster with direct role dropdown
            document.getElementById("player-count").innerText = state.players.length;
            const plist = document.getElementById("players-list");
            const ICON = (n) => `<svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-${{n}}"/></svg>`;
            const rows = state.players.map(p => {{
                const role = p.is_voting_guesser ? "voter" : (p.is_guesser ? "guesser" : (p.is_truth_teller ? "truth_teller" : "liar"));
                const roleSel = `
                    <select class="role-select role-${{role}}" aria-label="Role for ${{escapeHtml(p.name)}}" onchange="this.blur(); changePlayerRole('${{p.id}}', this.value)">
                        <option value="voter" ${{role === "voter" ? "selected" : ""}}>Guesser (Voter)</option>
                        <option value="guesser" ${{role === "guesser" ? "selected" : ""}}>Guesser (Consultant)</option>
                        <option value="truth_teller" ${{role === "truth_teller" ? "selected" : ""}}>Truth Teller</option>
                        <option value="liar" ${{role === "liar" ? "selected" : ""}}>Liar</option>
                    </select>`;
                const topic = !p.topic ? `<span class="muted">—</span>` : (revealedTopics[p.id]
                    ? `<button class="link-btn" onclick="toggleTopic('${{p.id}}')" title="Hide topic">${{escapeHtml(p.topic)}}</button>`
                    : `<button class="link-btn muted" onclick="toggleTopic('${{p.id}}')">${{ICON("eye")}} Show</button>`);
                return `
                    <tr class="prow ${{p.is_guesser ? "is-guesser" : (p.is_truth_teller ? "is-truth" : "")}}">
                        <td class="pname">${{escapeHtml(p.name)}}${{p.account ? ` <span class="acct-tag" title="Permanent account">${{ICON("user")}}</span>` : ""}}</td>
                        <td>${{roleSel}}</td>
                        <td class="ptopic">${{topic}}</td>
                        <td class="pscore">${{p.score}}</td>
                        <td class="pact">
                            <button class="icon-btn" title="Add a point" aria-label="Add a point to ${{escapeHtml(p.name)}}" onclick="adjustScore('${{p.id}}', 1)">+1</button>
                            <button class="icon-btn danger" title="Remove player" aria-label="Remove ${{escapeHtml(p.name)}}" onclick="removePlayer('${{p.id}}')">${{ICON("x")}}</button>
                        </td>
                    </tr>`;
            }}).join("");
            const rosterHtml = state.players.length ? `
                <table class="roster-table">
                    <thead><tr><th>Player</th><th>Role</th><th>Topic</th><th>Pts</th><th></th></tr></thead>
                    <tbody>${{rows}}</tbody>
                </table>` : `<div class="muted" style="padding: 8px 0;">No players yet. Share the QR code or add someone above.</div>`;
            // Re-render only on change, and never under an open role dropdown (polling would close it).
            const rosterBusy = document.activeElement && document.activeElement.tagName === "SELECT" && plist.contains(document.activeElement);
            if (plist.dataset.html !== rosterHtml && !rosterBusy) {{
                plist.innerHTML = rosterHtml;
                plist.dataset.html = rosterHtml;
            }}

            // Guesser Accusation Dropdown / Multi-Select (no topic spoiler)
            const gBox = document.getElementById("guesser-voting-box");
            const voterId = state.voting_guesser_id || state.guesser_id;
            const guesser = state.players.find(p => p.id === voterId);
            if (!guesser) {{
                gBox.innerHTML = '<span style="color: var(--text-muted);">Assign a Guesser to enable voting.</span>';
            }} else {{
                const truthCount = state.truth_teller_count || state.target_truth_teller_count || 1;
                if (truthCount <= 1) {{
                    let options = `<option value="">-- Select who the Guesser accuses of telling the truth --</option>`;
                    state.players.forEach(cand => {{
                        if (!cand.is_guesser) {{
                            const isSel = (Array.isArray(guesser.voted_for) ? guesser.voted_for.includes(cand.id) : guesser.voted_for === cand.id);
                            const sel = isSel ? "selected" : "";
                            options += `<option value="${{cand.id}}" ${{sel}}>${{escapeHtml(cand.name)}}</option>`;
                        }}
                    }});
                    gBox.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <select onchange="castVote('${{guesser.id}}', this.value)" style="background: #171513; border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: 6px; font-size: 0.88rem; flex: 1;">
                                ${{options}}
                            </select>
                        </div>
                        ${{guesser.voted_for ? `<div style="margin-top: 8px; font-size: 0.82rem; color: #7cc19a;">✓ Accusation recorded! Result revealed automatically.</div>` : ''}}
                    `;
                }} else {{
                    let options = "";
                    state.players.forEach(cand => {{
                        if (!cand.is_guesser) {{
                            const isSel = (Array.isArray(guesser.voted_for) ? guesser.voted_for.includes(cand.id) : guesser.voted_for === cand.id);
                            const sel = isSel ? "selected" : "";
                            options += `<option value="${{cand.id}}" ${{sel}}>${{escapeHtml(cand.name)}}</option>`;
                        }}
                    }});
                    gBox.innerHTML = `
                        <div style="font-size: 0.82rem; color: #ead29c; margin-bottom: 6px;">Select all ${{truthCount}} suspects accused by the Guesser:</div>
                        <div style="display: flex; gap: 8px; align-items: flex-start;">
                            <select id="admin-guesser-multi-vote" multiple size="3" style="background: #171513; border: 1px solid var(--border); color: var(--text); padding: 6px; border-radius: 6px; font-size: 0.88rem; flex: 1;">
                                ${{options}}
                            </select>
                            <button class="btn btn-warning" onclick="adminSubmitMultiVote('${{guesser.id}}', ${{truthCount}})" style="padding: 8px 14px; font-weight: 700; font-size: 0.82rem;">Cast Accusations</button>
                        </div>
                        ${{guesser.voted_for ? `<div style="margin-top: 8px; font-size: 0.82rem; color: #7cc19a;">✓ Accusation recorded! Result revealed automatically.</div>` : ''}}
                    `;
                    const selElem = document.getElementById("admin-guesser-multi-vote");
                    if (selElem) attachToggleBehavior(selElem);
                }}
            }}

            // Render Live Terminal & Server Logs
            const logsContainer = document.getElementById("logs-list");
            if (logsContainer) {{
                const logs = state.logs || [];
                const countBadge = document.getElementById("logs-count");
                if (countBadge) countBadge.innerText = `${{logs.length}} event${{logs.length === 1 ? '' : 's'}}`;

                if (logs.length === 0) {{
                    logsContainer.innerHTML = '<div style="color: #8a8276; font-style: italic; padding: 6px;">Waiting for server events... Terminal active.</div>';
                }} else {{
                    const html = logs.map(log => {{
                        const time = escapeHtml(log.timestamp || "");
                        const lvl = escapeHtml(log.level || "INFO").toUpperCase();
                        const msg = escapeHtml(log.message || "");
                        let badgeClass = "log-badge log-info";
                        if (lvl === "WARN" || lvl === "WARNING" || lvl === "ERROR") {{
                            badgeClass = "log-badge log-warn";
                        }} else if (lvl === "ACTION" || lvl === "EVENT") {{
                            badgeClass = "log-badge log-action";
                        }}
                        return `<div class="log-entry">
                            <span class="log-time">[${{time}}]</span>
                            <span class="${{badgeClass}}">[${{lvl}}]</span>
                            <span class="log-msg">${{msg}}</span>
                        </div>`;
                    }}).join("");

                    if (logsContainer.dataset.lastLogCount !== String(logs.length) || logsContainer.innerHTML !== html) {{
                        logsContainer.innerHTML = html;
                        logsContainer.dataset.lastLogCount = String(logs.length);
                        if (!window.logsUserScrolled) {{
                            logsContainer.scrollTop = logsContainer.scrollHeight;
                        }}
                    }}
                }}
            }}

            // Render Topic History Drawer if open
            renderTopicHistoryDrawer();
        }}

        let topicDrawerOpen = false;
        let drawerMasked = false;

        function toggleTopicHistoryDetails() {{
            topicDrawerOpen = !topicDrawerOpen;
            const drawer = document.getElementById("topic-history-drawer");
            const btn = document.getElementById("toggle-topic-drawer-btn");
            if (drawer) drawer.style.display = topicDrawerOpen ? "block" : "none";
            if (btn) btn.innerText = topicDrawerOpen ? "✖ Close History" : "View Used";
            if (topicDrawerOpen) renderTopicHistoryDrawer();
        }}

        function toggleDrawerMask() {{
            drawerMasked = !drawerMasked;
            const btn = document.getElementById("toggle-drawer-mask-btn");
            if (btn) btn.innerText = drawerMasked ? "Show Details" : "Hide Details";
            renderTopicHistoryDrawer();
        }}

        function renderTopicHistoryDrawer() {{
            if (!topicDrawerOpen || !gameState) return;
            const tList = document.getElementById("drawer-truth-list");
            const lList = document.getElementById("drawer-lies-list");
            const tCount = document.getElementById("drawer-truth-count");
            const lCount = document.getElementById("drawer-lies-count");

            const trueStmts = gameState.used_true_statements || [];
            const falseStmts = gameState.used_false_statements || [];

            if (tCount) tCount.innerText = trueStmts.length;
            if (lCount) lCount.innerText = falseStmts.length;

            if (tList) {{
                if (trueStmts.length === 0) {{
                    tList.innerHTML = `<div style="color: #8a8276; font-style: italic; padding: 12px 6px; text-align: center;">No true statements used yet.</div>`;
                }} else {{
                    tList.innerHTML = trueStmts.map(s => {{
                        if (drawerMasked) {{
                            return `<div style="padding: 6px; background: rgba(0,0,0,0.25); border-radius: 4px; border-left: 2px solid #5ea67e; font-size: 0.75rem; color: #a39b8c;">Round ${{s.round || 1}} &bull; ${{escapeHtml(s.player_name || 'Truth Teller')}} (Masked)</div>`;
                        }}
                        const cat = s.category ? ` &bull; ${{escapeHtml(s.category)}}` : '';
                        return `
                            <div style="padding: 6px 8px; background: rgba(0,0,0,0.25); border-radius: 4px; border-left: 2px solid #5ea67e;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-weight: 700; color: #9fd2b3; font-size: 0.75rem;">${{escapeHtml(s.topic || 'Topic')}}${{cat}}</span>
                                    <span style="font-size: 0.72rem; color: #bfe0cb;">R${{s.round || 1}} &bull; ${{escapeHtml(s.player_name || '')}}</span>
                                </div>
                                <div style="font-size: 0.78rem; color: #ece7dc; margin-top: 2px; line-height: 1.35;">${{escapeHtml(s.statement || '')}}</div>
                            </div>
                        `;
                    }}).join('');
                }}
            }}

            if (lList) {{
                if (falseStmts.length === 0) {{
                    lList.innerHTML = `<div style="color: #8a8276; font-style: italic; padding: 12px 6px; text-align: center;">No false statements used yet.</div>`;
                }} else {{
                    lList.innerHTML = falseStmts.map(s => {{
                        if (drawerMasked) {{
                            return `<div style="padding: 6px; background: rgba(0,0,0,0.25); border-radius: 4px; border-left: 2px solid #e0675a; font-size: 0.75rem; color: #a39b8c;">Round ${{s.round || 1}} &bull; ${{escapeHtml(s.player_name || 'Liar')}} (Masked)</div>`;
                        }}
                        const cat = s.category ? ` &bull; ${{escapeHtml(s.category)}}` : '';
                        return `
                            <div style="padding: 6px 8px; background: rgba(0,0,0,0.25); border-radius: 4px; border-left: 2px solid #e0675a;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-weight: 700; color: #eda79e; font-size: 0.75rem;">${{escapeHtml(s.topic || 'Topic')}}${{cat}}</span>
                                    <span style="font-size: 0.72rem; color: #eda79e;">R${{s.round || 1}} &bull; ${{escapeHtml(s.player_name || '')}}</span>
                                </div>
                                <div style="font-size: 0.78rem; color: #f8ebe8; margin-top: 2px; line-height: 1.35;">${{escapeHtml(s.statement || '')}}</div>
                            </div>
                        `;
                    }}).join('');
                }}
            }}
        }}

        function escapeHtml(str) {{
            if (!str) return '';
            return str.replace(/[&<>"']/g, function(m) {{
                return {{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }}[m];
            }});
        }}

        function setRoleMode(mode) {{
            api("set_role_mode", {{ mode }});
        }}

        function updateRoleCounts() {{
            const gCount = parseInt(document.getElementById("admin-guesser-count").value) || 1;
            const ttCount = parseInt(document.getElementById("admin-truth-count").value) || 1;
            api("set_role_counts", {{ guesser_count: gCount, truth_teller_count: ttCount, apply_now: true }});
        }}

        function changePlayerRole(pid, val) {{
            if (val === "voter") {{
                api("set_voting_guesser", {{ player_id: pid }});
            }} else if (val === "guesser") {{
                api("set_role", {{ player_id: pid, role: "guesser", is_voter: false }});
            }} else if (val === "truth_teller") {{
                api("set_role", {{ player_id: pid, role: "truth_teller" }});
            }} else if (val === "liar") {{
                api("set_role", {{ player_id: pid, role: "liar" }});
            }}
        }}

        function attachToggleBehavior(selectElem, onChangeCallback) {{
            if (!selectElem) return;
            selectElem.addEventListener("mousedown", function(e) {{
                if (!this.multiple) return;
                const opt = e.target;
                if (opt && opt.tagName === "OPTION") {{
                    e.preventDefault();
                    opt.selected = !opt.selected;
                    this.focus();
                    if (onChangeCallback) onChangeCallback(this);
                }}
            }});
        }}

        function onGuesserMultiChange(selectElem) {{
            const selectedIds = Array.from(selectElem.selectedOptions).map(o => o.value).filter(Boolean);
            if (selectedIds.length > 0) {{
                const currentVoter = (gameState && gameState.voting_guesser_id) || null;
                const voterId = (currentVoter && selectedIds.includes(currentVoter)) ? currentVoter : selectedIds[0];
                api("set_guessers", {{ player_ids: selectedIds, voter_id: voterId }});
            }}
        }}

        function chooseLeadVoter(pid) {{
            if (pid) {{
                api("set_voting_guesser", {{ player_id: pid }});
            }}
        }}

        function onTruthTellerMultiChange(selectElem) {{
            const selectedIds = Array.from(selectElem.selectedOptions).map(o => o.value).filter(Boolean);
            if (selectedIds.length > 0) {{
                api("set_truth_tellers", {{ player_ids: selectedIds }});
            }}
        }}

        function chooseGuesser(pid) {{
            if (pid) api("set_voting_guesser", {{ player_id: pid }});
        }}

        function chooseTruthTeller(pid) {{
            if (pid) api("set_truth_teller", {{ player_id: pid }});
        }}

        function setPhase(p) {{ api("set_phase", {{ phase: p }}); }}
        function startRoundFromLobby() {{
            if (gameState && gameState.role_requirements && !gameState.role_requirements.valid) {{
                alert(gameState.role_requirements.error);
                return;
            }}
            setPhase('setup');
        }}
        function nextPhase() {{ api("next_phase"); }}
        function randomizeRoles() {{ api("randomize_roles"); }}
        function newTopics() {{ document.getElementById("new-topics-dialog").showModal(); }}
        let _packSig = "";
        function renderPacks(list) {{
            const el = document.getElementById("pack-list");
            const sig = JSON.stringify(list);
            if (!el || sig === _packSig) return;
            _packSig = sig;
            el.innerHTML = list.map(p => `
                <label class="pack-item">
                    <input type="checkbox" value="${{escapeHtml(p.id)}}" ${{p.selected ? "checked" : ""}} onchange="savePacks()">
                    <span class="pack-name">${{escapeHtml(p.name)}}</span>
                    <span class="pack-count">${{p.used}} / ${{p.total}} used</span>
                </label>`).join("");
        }}
        let _acctSig = "";
        function renderSettings(state) {{
            const st = state.settings || {{}};
            const mm = document.getElementById("mm-" + (st.match_mode || "off"));
            if (mm && !mm.checked) mm.checked = true;
            const ms = state.match_status || {{}}, msEl = document.getElementById("match-status");
            if (msEl) {{
                const prof = `${{ms.profiles || 0}}/${{(state.players || []).length}} players set interests`;
                const emb = {{ ready: "embeddings ready", working: `embedding topics… (${{ms.cached || 0}} cached)`, offline: "embeddings offline: random deal", idle: "" }}[ms.state] || "";
                const txt = st.match_mode === "expertise" ? `${{prof}} · ${{emb}}` : st.match_mode === "tags" ? prof : "";
                if (msEl.textContent !== txt) msEl.textContent = txt;
                msEl.title = ms.error || "";
                msEl.classList.toggle("bad", st.match_mode === "expertise" && ms.state === "offline");
            }}
            ["use_global", "use_user", "lying_facts", "hide_facts", "fair_roles"].forEach(k => {{
                const el = document.getElementById("set-" + k);
                if (el && document.activeElement !== el) el.checked = !!st[k];
            }});
            const im = document.getElementById("set-idle_minutes");
            if (im && document.activeElement !== im) im.value = st.idle_minutes || 60;
            const bc = document.getElementById("blocked-topics-count");
            if (bc) bc.innerText = state.blocked_topics_count || 0;
            const list = state.accounts || [];
            const sig = JSON.stringify(list);
            const el = document.getElementById("account-list");
            if (!el || sig === _acctSig) return;
            _acctSig = sig;
            el.innerHTML = list.length ? list.map(a => `
                <div class="account-row${{a.reset_requested ? " reset-requested" : ""}}" data-id="${{escapeHtml(a.id)}}" data-name="${{escapeHtml(a.name)}}">
                    <span class="pack-name">${{escapeHtml(a.name)}}${{a.reset_requested ? ` <span class="reset-note">forgot password: reset it</span>` : (a.must_change ? ` <span class="pack-count">(temp password given)</span>` : "")}}</span>
                    <span class="pack-count">${{a.score_total}} pts &bull; ${{a.wins}}/${{a.games}} games won &bull; ${{a.rounds}} rounds &bull; ${{a.seen}} topics seen</span>
                    <button class="btn btn-sm${{a.reset_requested ? " btn-warning" : ""}}" onclick="resetPassword(this.parentElement.dataset)">Reset password</button>
                    <button class="btn btn-sm" onclick="clearAccountHistory(this.parentElement.dataset)">Clear history</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteAccount(this.parentElement.dataset)">Delete</button>
                </div>`).join("") : `<div class="pack-count">No permanent accounts yet.</div>`;
        }}
        // Truth source links: the live page and the archived offline copy (PDFs open in the bundled pdf.js viewer).
        function srcLinks(s) {{
            const off = !s.archive ? "" : s.archive.endsWith(".pdf")
                ? `/archive/_pdfjs/web/viewer.html?file=${{encodeURIComponent("/archive/" + s.archive)}}#pagemode=none&zoom=page-width` : `/archive/${{encodeURIComponent(s.archive)}}`;
            return [escapeHtml(s.journal || s.publisher || ""), s.url ? `<a href="${{escapeHtml(s.url)}}" target="_blank" rel="noopener">Link</a>` : "",
                    off ? `<a href="${{off}}" target="_blank" rel="noopener">Offline copy</a>` : ""].filter(Boolean).join(" · ")
                + (s.institution || s.year ? `<br>${{escapeHtml([s.institution, s.year].filter(Boolean).join(" · "))}}` : "");
        }}
        async function loadReviews() {{
            const el = document.getElementById("review-list");
            try {{
                const rows = (await (await fetch("/api/reviews", {{ cache: "no-store" }})).json()).reviews || [];
                const by = {{}};
                rows.forEach(r => {{ const k = r.topic_id || r.topic; (by[k] = by[k] || {{ topic: r.topic, side: r.side, scores: [], notes: [] }}); by[k].scores.push(r.score); if (r.text) by[k].notes.push(`${{r.player_name}}: ${{r.text}}`); }});
                const list = Object.entries(by).map(([k, v]) => ({{ k, ...v, avg: v.scores.reduce((a, b) => a + b, 0) / v.scores.length }})).sort((a, b) => a.avg - b.avg);
                el.innerHTML = list.length ? `<div class="pack-count" style="margin: 6px 0;">${{rows.length}} reviews of ${{list.length}} statements, worst first</div>` + list.map(v => `
                    <div class="account-row" title="${{escapeHtml(v.notes.join("\\n"))}}">
                        <span class="pack-name">${{escapeHtml(v.topic || v.k)}} <span class="pack-count">(${{v.side}})</span></span>
                        <span class="pack-count">${{v.avg.toFixed(1)}}/10 &bull; ${{v.scores.length}} review${{v.scores.length > 1 ? "s" : ""}}${{v.notes.length ? " &bull; " + escapeHtml(v.notes[0].slice(0, 90)) : ""}}</span>
                    </div>`).join("") : '<div class="pack-count">No reviews yet.</div>';
            }} catch (e) {{
                el.innerHTML = '<div class="pack-count">Could not load reviews.</div>';
            }}
        }}
        function setMatchMode(value) {{ api("set_setting", {{ name: "match_mode", value }}); }}
        function saveSetting(el) {{ api("set_setting", {{ name: el.id.slice(4), value: el.checked }}); }}
        function clearAccountHistory(d) {{ if (confirm(`Clear the topic history of ${{d.name}}? Topics they've heard can be dealt to them again.`)) api("clear_account_history", {{ account_id: d.id }}); }}
        async function resetPassword(d) {{
            if (!confirm(`Give ${{d.name}} a new temporary password? Their current one stops working.`)) return;
            const r = await api("reset_password", {{ account_id: d.id }});
            if (r && r.temp_password) prompt(`Temporary password for ${{d.name}}. They enter it under "Log back in", then pick their own:`, r.temp_password);
        }}
        function deleteAccount(d) {{ if (confirm(`Delete the account ${{d.name}} (score and history)?`)) api("delete_account", {{ account_id: d.id }}); }}
        function savePacks() {{
            const ids = [...document.querySelectorAll("#pack-list input:checked")].map(i => i.value);
            _packSig = "";  // force a re-render so a rejected selection snaps back
            api("set_packs", {{ pack_ids: ids }});
        }}
        function clearTopicHistory() {{ if(confirm("Clear the global topic history? Per-player histories are kept.")) api("clear_topic_history"); }}
        function revealTruth() {{ api("reveal"); }}
        function nextRound() {{ api("next_round"); }}
        function resetGame() {{ if(confirm("Reset scores? Everyone's points and roles go back to zero and temporary players are signed out. Nobody gets a win (End Game books one).")) api("reset_game"); }}
        function terminateToLobby() {{ if(confirm("End the game? The player with the most points gets the win on the leaderboard, scores reset and a fresh lobby starts.")) api("end_game"); }}
        function removePlayer(pid) {{ api("remove_player", {{ player_id: pid }}); }}
        function adjustScore(pid, delta) {{ api("adjust_score", {{ player_id: pid, delta }}); }}
        function castVote(voterId, targetId) {{
            if (!targetId) return;
            const targetIds = Array.isArray(targetId) ? targetId : [targetId];
            api("cast_vote", {{ voter_id: voterId, target_id: targetId, target_ids: targetIds }});
        }}
        function adminSubmitMultiVote(guesserId, expectedCount) {{
            const selElem = document.getElementById("admin-guesser-multi-vote");
            if (!selElem) return;
            const selectedIds = Array.from(selElem.selectedOptions).map(o => o.value).filter(Boolean);
            if (selectedIds.length !== expectedCount) {{
                alert("Please select exactly " + expectedCount + " suspects for the accusation.");
                return;
            }}
            api("cast_vote", {{ voter_id: guesserId, target_ids: selectedIds }});
        }}
        function addPlayer() {{
            const inp = document.getElementById("new-player-name");
            const val = inp.value.trim();
            if (val) {{
                api("add_player", {{ name: val }});
                inp.value = "";
            }}
        }}

        window.logsUserScrolled = false;
        const logsEl = document.getElementById("logs-list");
        if (logsEl) {{
            logsEl.addEventListener("scroll", () => {{
                const atBottom = logsEl.scrollHeight - logsEl.scrollTop <= logsEl.clientHeight + 30;
                window.logsUserScrolled = !atBottom;
            }});
        }}

        setInterval(fetchState, 1000);
        fetchState();
    </script>
</body>
</html>
"""

def get_qr_html(port: int, lan_ip: str, base_url: Optional[str] = None) -> str:
    primary_join_url = f"{base_url.rstrip('/')}/join" if base_url else f"http://{lan_ip}:{port}/join"
    join_url_lan = f"http://{lan_ip}:{port}/join"
    join_url_local = f"http://127.0.0.1:{port}/join"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Join Lobby - QR Code</title>
    <link rel="stylesheet" href="/static/app.css">
    <style>
        :root {{
            --bg-dark: #0e0d0c;
            --card-bg: #171513;
            --primary: #e9e4d8;
            --success: #5ea67e;
            --text-main: #f1ece2;
            --text-muted: #a39b8c;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: var(--font-ui);
        }}
        body {{
            background: radial-gradient(circle at 50% 20%, #1d1a17 0%, var(--bg-dark) 100%);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }}
        .container {{
            max-width: 680px;
            width: 100%;
            text-align: center;
        }}
        .badge-tag {{
            display: inline-block;
            background: rgba(233,228,216, 0.2);
            border: 1px solid rgba(233,228,216, 0.5);
            color: #e9e4d8;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
            margin-bottom: 12px;
        }}
        h1 {{
            font-size: 2.2rem;
            font-weight: 900;
            margin-bottom: 8px;
            background: #f6f1e7;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        p.subtitle {{
            font-size: 1.05rem;
            color: var(--text-muted);
            margin-bottom: 24px;
        }}

        .qr-card {{
            background: var(--card-bg);
            border: 1px solid #2a2622;
            border-radius: 24px;
            padding: 32px;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
            display: inline-block;
            margin-bottom: 24px;
        }}
        .qr-wrapper {{
            background: #f6f1e7;
            padding: 20px;
            border-radius: 16px;
            display: inline-block;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            margin-bottom: 18px;
        }}
        .qr-wrapper img {{
            display: block;
            width: 280px;
            height: 280px;
        }}

        .link-pill {{
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid #2e2a25;
            border-radius: 12px;
            padding: 10px 16px;
            font-family: var(--font-mono);
            font-size: 1.05rem;
            color: #9fd2b3;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-bottom: 14px;
            word-break: break-all;
        }}
        .btn {{
            background: var(--primary);
            color: var(--paper-ink);
            border: none;
            padding: 8px 14px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        .btn:hover {{ background: #d8d0bd; }}

        .network-select {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 6px;
        }}
        .network-select a {{
            color: #e2d6b8;
            text-decoration: underline;
            cursor: pointer;
            margin: 0 4px;
        }}

        .roster-card {{
            background: rgba(23,21,19, 0.8);
            border: 1px solid #2a2622;
            border-radius: 16px;
            padding: 20px;
            margin-top: 10px;
        }}
        .roster-title {{
            font-size: 0.95rem;
            font-weight: 700;
            color: #e9e4d8;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .player-chips {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: center;
        }}
        .chip {{
            background: #201d1a;
            border: 1px solid #36312b;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.9rem;
            font-weight: 600;
            color: #e2dccf;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .chip.is-guesser {{
            border-color: #d9a441;
            color: #d9a441;
        }}
        .dot-green {{
            width: 8px;
            height: 8px;
            background: var(--success);
            border-radius: 50%;
        }}
    </style>
</head>
<body class="theme-noir fx-grain fx-spotlight">
    <div class="container">
        <div class="badge-tag">Player Mobile Lobby</div>
        <h1>Scan to Join Game</h1>
        <p class="subtitle">Open your iPhone or Android camera to enter the lobby.</p>

        <div class="qr-card">
            <div class="qr-wrapper" id="qr-container">
                <img id="qr-img" src="/api/qr.svg?url={primary_join_url}" alt="Join Lobby QR Code">
            </div>

            <div class="link-pill">
                <span id="current-url">{primary_join_url}</span>
                <button class="btn" onclick="copyLink()">Copy</button>
            </div>

            <div class="network-select">
                Target: 
                <a onclick="switchUrl('{primary_join_url}', true)">Web URL</a> | 
                <a onclick="switchUrl('{join_url_lan}', true)">Wi-Fi LAN ({lan_ip})</a> | 
                <a onclick="switchUrl('{join_url_local}', false)">Localhost (127.0.0.1)</a>
            </div>
        </div>

        <div class="roster-card">
            <div class="roster-title">
                Players Connected (<span id="connected-count">0</span>)
            </div>
            <div class="player-chips" id="player-chips">
                <span style="color: var(--text-muted); font-size: 0.85rem;">Waiting for players to scan and enter names...</span>
            </div>
            <div id="qr-standings-card" style="display: none; margin-top: 16px; border-top: 1px solid #2a2622; padding-top: 14px;"></div>
        </div>

        <div style="margin-top: 20px; display: flex; justify-content: center; gap: 14px; font-size: 0.85rem;">
            <a href="/admin/control" target="_blank" style="color: #9fd2b3; text-decoration: none; font-weight: 700;">
                Stage Controller (Zero Spoilers) &rarr;
            </a>
            <span style="color: #4a443b;">&bull;</span>
            <a href="/display" target="_blank" style="color: #e2d6b8; text-decoration: none;">
                Public Display &rarr;
            </a>
            <span style="color: #4a443b;">&bull;</span>
            <a href="/admin" target="_blank" style="color: #d9a441; text-decoration: none; opacity: 0.85;">
                Full Admin Dossier (Spoilers) &rarr;
            </a>
        </div>
    </div>

    <script>
        let currentUrl = "{join_url_lan}";

        function switchUrl(url, isLan) {{
            currentUrl = url;
            document.getElementById("current-url").innerText = url;
            document.getElementById("qr-img").src = "/api/qr.svg?url=" + encodeURIComponent(url);
        }}

        function copyLink() {{
            navigator.clipboard.writeText(currentUrl).then(() => {{
                alert("Copied join link to clipboard: " + currentUrl);
            }}).catch(() => {{
                prompt("Copy this URL:", currentUrl);
            }});
        }}

        async function updateLobby() {{
            try {{
                const res = await fetch("/api/state?role=player&_t=" + Date.now(), {{ cache: "no-store" }});
                const state = await res.json();
                
                document.getElementById("connected-count").innerText = (state.players || []).length;
                const container = document.getElementById("player-chips");
                
                if (!state.players || state.players.length === 0) {{
                    container.innerHTML = '<span style="color: var(--text-muted); font-size: 0.85rem;">Waiting for players to scan and enter names...</span>';
                }} else {{
                    container.innerHTML = "";
                    state.players.forEach(p => {{
                        const chip = document.createElement("div");
                        chip.className = "chip" + (p.is_guesser ? " is-guesser" : "");
                        const guesserTag = p.is_guesser ? (p.is_voting_guesser ? ' (Lead Guesser)' : ' (Guesser)') : '';
                        chip.innerHTML = `<span class="dot-green"></span> <span>${{escapeHtml(p.name)}}${{guesserTag}}</span>`;
                        container.appendChild(chip);
                    }});
                }}

                // Standings table in QR tab
                const standingsCard = document.getElementById("qr-standings-card");
                if (standingsCard) {{
                    if (state.standings && state.standings.length > 0 && (state.phase === "reveal" || state.round > 1)) {{
                        let rows = state.standings.map((s, idx) => {{
                            let medal = `${{idx + 1}}.`;
                            return `
                                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                                    <td style="padding: 6px; text-align: center; font-weight: 800;">${{medal}}</td>
                                    <td style="padding: 6px; font-weight: 700; color: #ece7dc;">${{escapeHtml(s.name)}}</td>
                                    <td style="padding: 6px; text-align: right; font-weight: 900; color: #d9a441;">${{s.score ?? 0}} pts</td>
                                </tr>
                            `;
                        }}).join("");
                        standingsCard.style.display = "block";
                        standingsCard.innerHTML = `
                            <div style="font-size: 0.88rem; font-weight: 800; color: #d9a441; margin-bottom: 8px; text-transform: uppercase;">
                                Current Standings (Round ${{state.round}})
                            </div>
                            <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
                                <tbody>${{rows}}</tbody>
                            </table>
                        `;
                    }} else {{
                        standingsCard.style.display = "none";
                    }}
                }}
            }} catch(e) {{
                console.error(e);
            }}
        }}

        function escapeHtml(str) {{
            if (!str) return '';
            return str.replace(/[&<>"']/g, function(m) {{
                return {{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }}[m];
            }});
        }}

        setInterval(updateLobby, 1500);
        updateLobby();
    </script>
</body>
</html>
"""

def get_join_html(port: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Play - One of These People Is Not Lying</title>
    <link rel="stylesheet" href="/static/app.css">
    <style>
        :root {{
            --bg-dark: var(--ink);
            --card-bg: #171513;
            --card-border: #2a2622;
            --primary: #e9e4d8;
            --guesser-color: #d9a441;
            --truth-color: #7cc19a;
            --liar-color: #e47f73;
            --text-main: #f1ece2;
            --text-muted: #a39b8c;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: var(--font-ui);
            -webkit-tap-highlight-color: transparent;
        }}
        body {{
            background: var(--bg-dark);
            color: var(--text-main);
            min-height: 100vh;
            padding: 14px 12px 28px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .mobile-card {{
            max-width: clamp(440px, 52vw, 760px);  /* phone: full width; desktop browser: wider with the window */
            width: 100%;
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 18px 16px;
            margin-top: 6px;
            box-shadow: var(--shadow);
            text-align: center;
            position: relative;
            z-index: 1;
        }}
        h1 {{
            font-size: 1.7rem;
            margin-bottom: 4px;
        }}
        .tagline {{
            font-size: 0.82rem;
            color: var(--text-muted);
            margin-bottom: 16px;
        }}

        input[type="text"]:focus, input[type="password"]:focus {{
            border-color: var(--paper-2);
        }}
        .join-tabs {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 4px;
            padding: 4px;
            margin: 4px 0 6px;
            background: var(--ink);
            border: 1px solid var(--line);
            border-radius: 10px;
        }}
        .join-tab {{
            min-height: 40px;
            border: 0;
            border-radius: 7px;
            background: transparent;
            color: var(--muted);
            font: 600 0.9rem var(--font-ui);
            cursor: pointer;
        }}
        .join-tab.active {{
            background: var(--ink-3);
            color: var(--text);
            box-shadow: inset 0 0 0 1px var(--line);
        }}
        #join-form .btn {{ margin-top: 8px; }}

        .btn {{
            width: 100%;
            min-height: 50px;
            background: var(--paper);
            color: var(--paper-ink);
            border: 1px solid var(--paper);
            padding: 12px 14px;
            border-radius: 10px;
            font-size: 1rem;
            font-weight: 700;
            cursor: pointer;
            transition: transform 0.1s ease, filter 0.15s ease;
        }}
        .btn:active {{
            transform: scale(0.98);
        }}

        /* Status Bar */
        .player-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 10px;
            margin-bottom: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .my-score {{ font: 600 0.74rem var(--font-mono); color: var(--guesser); background: rgba(217,164,65,0.14); border-radius: 6px; padding: 2px 7px; }}
        .my-score:empty {{ display: none; }}
        .player-identity {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.88rem;
            font-weight: 700;
            color: #e9e4d8;
        }}
        .lb-btn {{ color: #d9a441; margin-left: auto; }}
        .lb-cols {{ font-size: 0.7rem; color: #a39b8c; }}
        .lb-sub {{ font-size: 0.7rem; color: #8a8276; font-weight: 500; }}
        .forgot-link {{ display: block; margin: 6px 0 2px; font-size: 0.78rem; color: #d9a441; text-decoration: underline; cursor: pointer; }}
        .change-btn {{
            font-size: 0.72rem;
            color: #8a8276;
            text-decoration: underline;
            cursor: pointer;
            margin-left: 4px;
        }}
        /* Phase change: a stamp slams over the screen, then the new card rises in. */
        #phase-stamp {{ position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; pointer-events: none; opacity: 0;
                        background: rgba(10,9,8,0.84); backdrop-filter: blur(3px); text-align: center; }}
        #phase-stamp b {{ display: inline-block; font: 700 2.1rem var(--font-display); letter-spacing: 0.12em; text-transform: uppercase;
                          padding: 0.3em 0.7em; border: 3px solid currentColor; border-radius: 6px; color: var(--stamp, #e9e4d8); }}
        #phase-stamp small {{ display: block; margin-top: 14px; font: 600 0.78rem var(--font-mono); letter-spacing: 0.3em; color: #a39b8c; }}
        #phase-stamp.go {{ animation: ps-bg 1.15s ease both; }}
        #phase-stamp.go b {{ animation: ps-stamp 1.15s cubic-bezier(0.2, 1.5, 0.4, 1) both; }}
        @keyframes ps-bg {{ 0% {{ opacity: 0; }} 14% {{ opacity: 1; }} 72% {{ opacity: 1; }} 100% {{ opacity: 0; }} }}
        @keyframes ps-stamp {{ 0% {{ opacity: 0; transform: rotate(-9deg) scale(2.3); }} 26% {{ opacity: 1; transform: rotate(-5deg) scale(1); }}
                               80% {{ opacity: 1; transform: rotate(-5deg) scale(1); }} 100% {{ opacity: 0; transform: rotate(-5deg) scale(0.94); }} }}
        #game-section.phase-in {{ animation: phase-in 0.6s 0.75s cubic-bezier(0.2, 0.8, 0.3, 1) both; }}
        @keyframes phase-in {{ from {{ opacity: 0; transform: translateY(16px); filter: blur(5px); }} }}
        @media (prefers-reduced-motion: reduce) {{
            #phase-stamp.go b {{ animation: none; }}
            #game-section.phase-in {{ animation: phase-in 0.3s ease both; }}
        }}
        details.interests {{ margin-top: 14px; border: 1px solid var(--line, #3a352e); border-radius: 10px; background: rgba(255,255,255,0.02); text-align: left; }}
        details.interests summary {{ list-style: none; cursor: pointer; display: flex; align-items: center; gap: 8px; padding: 10px 12px;
                                     font: 600 0.72rem var(--font-mono); letter-spacing: 0.14em; text-transform: uppercase; color: #a39b8c; }}
        details.interests summary::-webkit-details-marker {{ display: none; }}
        .int-sum {{ flex: 1; text-transform: none; letter-spacing: 0; font: 500 0.78rem var(--font-body, inherit); color: #d8d0bd; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .pencil {{ font-size: 0.95rem; color: #d9a441; }}
        details.interests[open] {{ padding-bottom: 12px; }}
        details.interests > :not(summary) {{ margin-left: 12px; margin-right: 12px; }}
        .int-mode {{ margin-top: 0; font-size: 0.78rem; color: #a39b8c; }}
        .int-tabs {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 16px; margin-bottom: 10px; }}
        .int-tab {{ position: relative; padding: 8px; border-radius: 8px; border: 1px solid #3a352e; background: #171513; color: #a39b8c; font-weight: 700; font-size: 0.85rem; }}
        .int-tab.on {{ color: #ece7dc; background: #24201b; }}
        .int-tab b {{ display: none; position: absolute; top: -8px; right: 6px; font: 700 0.58rem var(--font-mono); letter-spacing: 0.12em; text-transform: uppercase;
                      background: #d9a441; color: #171513; padding: 1px 5px; border-radius: 4px; }}
        .int-tab.in-use {{ border-color: #d9a441; box-shadow: 0 0 0 1px rgba(217,164,65,0.35); }}
        .int-tab.in-use b {{ display: block; }}
        .tag-tools {{ display: flex; gap: 8px; }}
        .tag-tools #tag-search {{ flex: 1 1 auto; min-width: 0; }}
        #tag-sort {{ flex: 0 0 auto; width: auto; background: #171513; border: 1px solid #3a352e; color: #ece7dc; border-radius: 8px; padding: 0 6px; font: inherit; font-size: 0.85rem; }}
        #tag-search, #exp-input {{ width: 100%; box-sizing: border-box; background: #171513; border: 1px solid #3a352e; color: #ece7dc; border-radius: 8px; padding: 8px 10px; font: inherit; font-size: 0.9rem; }}
        #exp-input {{ resize: vertical; display: block; }}
        #resume-note:empty, #tag-note:empty {{ display: none; }}
        #auto-tags-btn {{ flex: 0 0 auto; width: auto; margin: 0; padding: 0 12px; }}
        .tag-chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; max-height: 210px; overflow-y: auto; }}
        .tag-chip {{ flex: 1 1 auto; text-align: center; padding: 5px 10px; border-radius: 999px; border: 1px solid #3a352e; background: transparent; color: #d8d0bd; font-size: 0.8rem; }}
        .tag-chip[aria-pressed="true"] {{ background: rgba(217,164,65,0.18); border-color: #d9a441; color: #f0d9a8; }}
        .tag-chip[aria-pressed="true"]::before {{ content: "✓ "; }}
        .tag-add {{ border-style: dashed; border-color: #d9a441; color: #f0d9a8; }}
        .exp-row {{ display: flex; justify-content: space-between; align-items: flex-start; margin-top: 2px; font-size: 0.75rem; color: #a39b8c; }}
        .exp-row #exp-count {{ line-height: 1; }}
        .exp-btns {{ display: flex; gap: 6px; margin-top: 4px; }}
        .icon-only {{ width: 36px; height: 36px; margin: 0; padding: 0; display: inline-flex; align-items: center; justify-content: center; }}
        .icon-only .icon {{ width: 18px; height: 18px; }}
        .tv-link {{ text-align: center; margin: 14px 0 4px; font-size: 0.8rem; }}
        .tv-link a {{ color: #a39b8c; text-decoration: none; }}
        .phase-badge {{
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            padding: 3px 8px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.08);
            color: #d3cbbb;
        }}

        /* Role Badges */
        .role-badge {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 6px;
            font: 600 0.95rem var(--font-mono);
            text-transform: uppercase;
            letter-spacing: 0.16em;
            margin: 4px 0 10px;
        }}
        .badge-guesser {{
            background: rgba(217,164,65, 0.15);
            color: var(--guesser-color);
            border: 1.5px solid var(--guesser-color);
        }}
        .badge-truth {{
            background: rgba(94,166,126, 0.15);
            color: var(--truth-color);
            border: 1.5px solid var(--truth-color);
        }}
        .badge-liar {{
            background: rgba(224,103,90, 0.15);
            color: var(--liar-color);
            border: 1.5px solid var(--liar-color);
        }}

        /* Guesser Team Banner */
        .team-banner {{
            background: rgba(217,164,65, 0.1);
            border: 1px solid rgba(217,164,65, 0.3);
            border-radius: 8px;
            padding: 8px 10px;
            margin-bottom: 10px;
            font-size: 0.84rem;
            color: #efdcaa;
            text-align: center;
        }}
        .team-subtext {{
            font-size: 0.76rem;
            color: #a39b8c;
            margin-top: 2px;
        }}

        .goal-pill {{
            display: inline-block;
            background: rgba(0, 0, 0, 0.25);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 0.8rem;
            font-weight: 600;
            color: #d3cbbb;
            margin-bottom: 8px;
        }}

        .topic-pill {{
            background: #201d1a;
            color: #e2d6b8;
            font: 600 0.88rem var(--font-mono);
            padding: 5px 12px;
            border-radius: 8px;
            display: inline-block;
            margin-bottom: 10px;
            border: 1px solid #36312b;
            max-width: 100%;
            word-break: break-word;
        }}

        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
        }}

        .statement-card {{
            position: relative;
            background: var(--ink);
            border: 1px solid var(--line-soft);
            border-radius: 10px;
            padding: 16px 14px;
            margin: 8px 0;
            text-align: left;
        }}
        .statement-label {{
            font: 600 0.7rem var(--font-mono);
            text-transform: uppercase;
            letter-spacing: 0.16em;
            margin-bottom: 8px;
        }}
        .statement-match {{ margin-top: 10px; padding-top: 8px; border-top: 1px dashed rgba(255,255,255,0.12); font: 600 0.78rem var(--font-mono); color: #c9c1b0; }}
        .statement-match b {{ font-size: 1rem; }}
        .statement-source {{ margin-top: 10px; padding-top: 8px; border-top: 1px dashed rgba(255,255,255,0.12); font: 500 0.72rem var(--font-mono); color: #a39b8c; overflow-wrap: anywhere; }}
        .statement-source a {{ color: #9fd2b3; }}
        .statement-text {{
            font: 400 0.98rem/1.6 var(--font-mono);
            color: #f1ece2;
            text-align: justify; hyphens: auto;
        }}

        /* Collapsible Facts Drawer */
        details.facts-drawer {{
            margin-top: 8px;
            background: rgba(94,166,126, 0.06);
            border: 1px solid rgba(94,166,126, 0.25);
            border-radius: 8px;
            padding: 8px 10px;
            text-align: left;
        }}
        summary.facts-summary {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            list-style: none;
            font-size: 0.78rem;
            font-weight: 700;
            color: #9fd2b3;
            cursor: pointer;
            user-select: none;
            outline: none;
        }}
        summary.facts-summary::-webkit-details-marker {{ display: none; }}
        summary.facts-summary .icon {{ transition: transform 0.18s ease; }}
        details[open] > summary.facts-summary .icon {{ transform: rotate(90deg); }}
        .facts-content {{
            overflow: hidden;
            font-size: 0.92rem;
            line-height: 1.5;
            color: #dcefe2;
            margin-top: 6px;
            border-top: 1px dashed rgba(94,166,126, 0.2);
            padding-top: 6px;
        }}
        .facts-content ul {{ margin: 0; padding-left: 1.15rem; }}
        .facts-content li + li {{ margin-top: 4px; }}
        /* Whiteout: correction tape drawn over each fact (hide_facts setting, questioning phase).
           Resting state is fully covered, so reduced-motion (no animation) still hides the text. */
        .redacted li {{ position: relative; color: transparent; user-select: none; }}
        .redacted li::after {{
            content: ""; position: absolute; inset: 2px -3px 1px -2px;
            background: #f2eee4; border-radius: 2px 5px 3px 2px;
            box-shadow: 0 1px 0 rgba(0,0,0,0.25), inset 0 -2px 0 rgba(0,0,0,0.06);
            transform-origin: left center;
            animation: whiteout 0.42s cubic-bezier(0.3, 0.7, 0.4, 1) backwards;
        }}
        .redacted li:nth-child(2)::after {{ animation-delay: 0.14s; }}
        .redacted li:nth-child(3)::after {{ animation-delay: 0.28s; }}
        .redacted li:nth-child(4)::after {{ animation-delay: 0.42s; }}
        .redacted li:nth-child(5)::after {{ animation-delay: 0.56s; }}
        @keyframes whiteout {{
            from {{ transform: scaleX(0) skewX(-8deg); opacity: 0.6; }}
            to {{ transform: scaleX(1) skewX(0); opacity: 1; }}
        }}

        details.facts-liar {{ background: rgba(224,103,90, 0.06); border-color: rgba(224,103,90, 0.3); }}
        details.facts-liar summary.facts-summary {{ color: #eda79e; }}
        details.facts-liar .facts-content {{ color: #f4dcd7; border-top-color: rgba(224,103,90, 0.25); }}
        .liar-tip {{
            margin-top: 8px;
            font-size: 0.78rem;
            color: #eda79e;
            background: rgba(224,103,90, 0.06);
            border: 1px solid rgba(224,103,90, 0.2);
            border-radius: 8px;
            padding: 6px 10px;
            line-height: 1.35;
        }}

        /* Suspects Roster */
        .roster-card {{
            margin-top: 12px;
            background: rgba(0, 0, 0, 0.25);
            border: 1px solid #201d1a;
            border-radius: 12px;
            padding: 10px 12px;
            text-align: left;
        }}
        .roster-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.76rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #a39b8c;
            margin-bottom: 6px;
        }}
        .roster-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 5px 8px;
            border-radius: 6px;
            margin-bottom: 3px;
            background: rgba(255, 255, 255, 0.02);
        }}
        .roster-name {{
            font-size: 0.84rem;
            font-weight: 700;
            color: #ece7dc;
        }}
        .roster-topic {{
            font: 600 0.75rem var(--font-mono);
            color: #e2d6b8;
            background: rgba(201,191,168, 0.12);
            padding: 2px 7px;
            border-radius: 5px;
            max-width: 55%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        /* Voting Buttons */
        .vote-btn {{
            width: 100%;
            background: #1a1816;
            border: 1.5px solid #36312b;
            color: var(--text);
            min-height: 48px;
            padding: 10px 12px;
            border-radius: 8px;
            font-size: 0.92rem;
            font-weight: 600;
            margin-bottom: 6px;
            cursor: pointer;
            text-align: left;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .vote-btn.selected {{
            background: rgba(217,164,65, 0.18);
            border-color: var(--guesser-color);
            color: #efdcaa;
        }}

        /* Results / Reveal Styling */
        .verdict-card {{ text-align: left; background: var(--ink-2); border: 1px solid var(--line); border-radius: 12px; padding: 14px; margin-bottom: 12px; }}
        .verdict-title {{ font: 650 1.6rem var(--font-display); line-height: 1.1; margin: 2px 0 6px; }}
        .verdict-note {{ font-size: 0.88rem; color: var(--paper-2); line-height: 1.45; }}
        .verdict-note strong {{ color: var(--text); }}
        .verdict-gain {{ display: inline-block; margin-top: 8px; font: 600 0.8rem var(--font-mono); color: var(--truth); background: rgba(124,193,154,0.12); padding: 2px 8px; border-radius: 6px; }}
        .verdict-rows {{ margin-top: 10px; }}
        .verdict-row {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 9px 4px; border-top: 1px solid var(--line-soft); }}
        .verdict-row.me {{ background: rgba(233,228,216,0.06); }}
        .vr-name {{ font-weight: 650; overflow-wrap: anywhere; }}
        .vr-name small {{ color: var(--muted); font-weight: 500; }}
        .vr-accused {{ font: 600 0.62rem var(--font-mono); letter-spacing: 0.14em; text-transform: uppercase; color: var(--guesser); border: 1px solid rgba(217,164,65,0.5); border-radius: 4px; padding: 1px 5px; margin-left: 4px; vertical-align: 2px; }}
        .vr-stamp {{ font-size: 0.72rem; padding: 2px 8px; border-width: 2px; flex: none; }}

        /* Mobile Leaderboard */
        .ready-btn {{
            display: block; width: 100%; margin-top: 14px; padding: 13px; border-radius: 12px; cursor: pointer;
            font: inherit; font-weight: 800; font-size: 1rem; letter-spacing: 0.3px;
            background: var(--paper, #e9e4d8); color: var(--paper-ink, #171513); border: 2px solid transparent;
            transition: background .15s, color .15s, border-color .15s;
        }}
        .ready-btn.on {{ background: rgba(124,193,154, 0.18); color: #7cc19a; border-color: #7cc19a; }}
        .ready-btn small {{ font-weight: 600; opacity: 0.8; }}
        .ready-wait {{ margin-top: 8px; font-size: 0.78rem; color: #a39b8c; text-align: center; }}
        .vr-src {{ margin: -4px 0 8px; font-size: 0.72rem; }}
        .review-btn {{ position: absolute; top: 8px; right: 8px; display: inline-flex; align-items: center; gap: 4px; background: transparent; border: 1px solid #3a352e; color: #a39b8c; border-radius: 999px; padding: 3px 9px; font: inherit; font-size: 0.7rem; cursor: pointer; }}
        .review-btn .icon {{ width: 12px; height: 12px; }}
        #review-dialog {{ margin: auto; width: min(92vw, 420px); background: #1a1816; color: #ece7dc; border: 1px solid rgba(233,228,216,0.35); border-radius: 12px; padding: 18px; }}
        #review-dialog::backdrop {{ background: rgba(0,0,0,0.6); }}
        #review-dialog textarea {{ width: 100%; box-sizing: border-box; background: #171513; border: 1px solid #3a352e; color: #ece7dc; border-radius: 8px; padding: 8px 10px; font: inherit; font-size: 0.9rem; }}
        .review-score {{ display: flex; align-items: center; gap: 10px; margin: 10px 0; }}
        .review-score input {{ flex: 1; }}
        .review-score output {{ font-weight: 900; font-size: 1.2rem; color: #d9a441; min-width: 2.5em; text-align: right; }}
        .review-actions {{ display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px; }}
        .review-actions .btn {{ width: auto; margin: 0; }}
        .lb-toggle {{ display: flex; border: 1px solid #3a352e; border-radius: 999px; overflow: hidden; }}
        .lb-toggle button {{ background: transparent; border: 0; color: #a39b8c; font: inherit; font-size: 0.78rem; font-weight: 700; padding: 5px 12px; cursor: pointer; }}
        .lb-toggle button[aria-pressed="true"] {{ background: #e9e4d8; color: #171513; }}
        .leaderboard-card {{
            background: rgba(0, 0, 0, 0.35);
            border: 1px solid #2a2622;
            border-radius: 12px;
            padding: 12px;
            margin-bottom: 10px;
            text-align: left;
        }}
        .leaderboard-title {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.92rem;
            font-weight: 800;
            color: #d9a441;
            margin-bottom: 8px;
        }}
        .leader-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 7px 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            font-size: 0.85rem;
        }}
        .leader-row:last-child {{
            border-bottom: none;
        }}
        .leader-row-me {{
            background: rgba(233,228,216, 0.18);
            border-radius: 6px;
        }}
    </style>
</head>
<body class="theme-noir fx-grain">
    <div class="mobile-card" id="join-section">
        <h1>Join The Game</h1>
        <p class="tagline">One of These People Is Not Lying</p>

        <div class="join-tabs" role="tablist">
            <button type="button" role="tab" id="tab-new" class="join-tab active" onclick="setJoinMode('new')">New player</button>
            <button type="button" role="tab" id="tab-back" class="join-tab" onclick="setJoinMode('back')">Log back in</button>
        </div>
        <form id="join-form" onsubmit="joinGame(event)" novalidate>
            <label class="field-label" for="player-name-input">Name</label>
            <input type="text" id="player-name-input" placeholder="Your name" maxlength="24" autocomplete="username" required>
            <label class="field-label" for="player-pass-input">Password <span id="pass-hint">(optional)</span></label>
            <input type="password" id="player-pass-input" placeholder="Password" maxlength="64" autocomplete="current-password">
            <div id="new-pass-row" style="display: none;">
                <label class="field-label" for="new-pass-input">New password <span>(4+ characters)</span></label>
                <input type="password" id="new-pass-input" placeholder="Choose your new password" maxlength="64" autocomplete="new-password">
            </div>
            <a id="forgot-link" class="forgot-link" role="button" tabindex="0" onclick="forgotPassword()">Forgot password?</a>
            <label class="check-row" id="permanent-row"><input type="checkbox" id="permanent-input" onchange="setJoinMode(joinMode)"> Keep a permanent account</label>
            <p class="field-hint" id="join-hint"></p>
            <div class="form-error" id="join-error" role="alert"></div>
            <button class="btn" type="submit" id="join-btn">Enter Lobby</button>
        </form>

        <div id="join-standings-preview" style="margin-top: 14px; display: none;"></div>
    </div>

    <!-- All-time leaderboard (saved accounts) -->
    <dialog id="review-dialog" aria-labelledby="review-title">
        <form method="dialog" onsubmit="return submitReview(event)">
            <div id="review-title" style="font-weight: 800; font-size: 1.05rem;">Review this statement</div>
            <p class="field-hint" style="margin: 4px 0 0;">How good is the statement and its facts? Helps us write better ones.</p>
            <div class="review-score"><input type="range" id="review-score" min="0" max="10" step="1" value="5" aria-label="Score from 0 to 10"
                oninput="document.getElementById('review-out').value = this.value + '/10'"><output id="review-out">5/10</output></div>
            <textarea id="review-text" rows="4" maxlength="1000" placeholder="What worked, what was confusing? (optional, 100 words max)" oninput="reviewCount()"></textarea>
            <div class="field-hint" id="review-count" style="text-align: right;">0/100 words</div>
            <p class="field-hint" id="review-status" role="status" style="margin: 4px 0 0;"></p>
            <div class="review-actions"><button type="button" class="btn btn-sm" onclick="document.getElementById('review-dialog').close()">Cancel</button>
                <button type="submit" class="btn btn-sm btn-primary" id="review-send">Send review</button></div>
        </form>
    </dialog>

    <div class="mobile-card" id="leaderboard-section" style="display: none;">
        <div class="player-bar">
            <a onclick="hideLeaderboard()" class="change-btn lb-btn" role="button" tabindex="0">&larr; Back</a>
            <div class="lb-toggle" role="group" aria-label="Leaderboard range">
                <button type="button" id="lb-all" aria-pressed="true" onclick="setLbMode('all')">All-time</button>
                <button type="button" id="lb-game" aria-pressed="false" onclick="setLbMode('game')">This game</button>
            </div>
        </div>
        <div class="leaderboard-card">
            <div class="leaderboard-title"><span>Leaderboard</span><span class="lb-cols" id="lb-cols">Wins &bull; Pts</span></div>
            <div id="leaderboard-rows"><div class="pack-count">Loading...</div></div>
        </div>
    </div>

    <!-- In-Game View -->
    <div class="mobile-card" id="game-section" style="display: none;">
        <div class="player-bar">
            <div class="player-identity">
                <span id="my-name-display">Player: ---</span>
                <span id="my-score-display" class="my-score"></span>
                <a onclick="showLeaderboard()" class="change-btn lb-btn" role="button" tabindex="0">Leaderboard</a>
                <a onclick="changeIdentity()" class="change-btn" role="button" tabindex="0">Sign out</a>
            </div>
            <div class="phase-badge" id="player-phase">Lobby</div>
        </div>

        <!-- Role Container -->
        <div id="role-container"></div>

        <!-- Voting View (Active for Guesser only; suspects wait) -->
        <div id="voting-section" style="display: none; text-align: left; margin-top: 12px;"></div>

        <!-- Interests: its own node, never re-rendered by polling, so typing is safe. -->
        <details class="interests" id="interests">
            <summary><span>Your interests</span><span class="int-sum" id="int-sum"></span><span class="pencil" aria-hidden="true">&#9998;</span></summary>
            <p class="int-mode" id="int-mode"></p>
            <div class="int-tabs" role="tablist">
                <button type="button" role="tab" class="int-tab" id="it-tags" onclick="intTab('tags')">Tags<b>in use</b></button>
                <button type="button" role="tab" class="int-tab" id="it-expertise" onclick="intTab('expertise')">Expertise<b>in use</b></button>
            </div>
            <div class="int-pane" id="ip-tags">
                <div class="tag-tools">
                    <input type="search" id="tag-search" placeholder="Search or add a tag..." oninput="renderTagChips()" autocomplete="off">
                    <select id="tag-sort" aria-label="Sort tags" onchange="localStorage.setItem('tag_sort', this.value); renderTagChips()">
                        <option value="relevance">Relevance</option>
                        <option value="az">A &#8594; Z</option>
                        <option value="za">Z &#8594; A</option>
                    </select>
                    <button type="button" class="btn btn-sm" id="auto-tags-btn" onclick="autoTags()" title="Pick tags from your expertise (existing tags first)">Auto</button>
                </div>
                <p class="field-hint" id="tag-note" role="status"></p>
                <div class="tag-chips" id="tag-chips"></div>
            </div>
            <div class="int-pane" id="ip-expertise" hidden>
                <textarea id="exp-input" maxlength="600" rows="5" oninput="expDirty = true; expCount()"
                    placeholder="Your field, research, hobbies: anything you could talk about for five minutes."></textarea>
                <div class="exp-row"><span id="exp-count"></span>
                    <span class="exp-btns"><button type="button" class="btn btn-sm icon-only" id="resume-btn" onclick="document.getElementById('resume-file').click()"
                        title="Upload a PDF resume: a local AI fills in your expertise and tags. The file isn't kept." aria-label="Upload a PDF resume"><svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-upload"/></svg></button>
                    <button type="button" class="btn btn-sm icon-only" id="exp-save" onclick="saveExpertise()" title="Save expertise" aria-label="Save expertise"><svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-save"/></svg></button></span></div>
                <input type="file" id="resume-file" accept="application/pdf,.pdf" hidden onchange="uploadResume(this)">
                <p class="field-hint" id="resume-note" role="status"></p>
            </div>
        </details>
    </div>
    <p class="tv-link"><a href="/display" target="_blank">Public Display &#8599;</a></p>
    <div id="phase-stamp" aria-hidden="true"><div><b></b><small></small></div></div>

    <script>
        function escapeHtml(str) {{
            if (str === null || str === undefined) return '';
            return String(str).replace(/[&<>"']/g, function(m) {{
                return {{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }}[m];
            }});
        }}

        // URL Parameter Override for Test Bench & Multi-Window Testing
        const urlParams = new URLSearchParams(window.location.search);
        const queryName = urlParams.get("name") || urlParams.get("player");
        const queryId = urlParams.get("player_id") || urlParams.get("id");
        const isUrlControlled = Boolean(queryName || queryId);

        // Track fold/accordion states so periodic polling does not reset user toggle interactions
        window.detailsFoldState = window.detailsFoldState || {{}};
        window.lastTrackedRound = undefined;

        function recordToggle(el) {{
            if (el && el.id) {{
                window.detailsFoldState[el.id] = el.open;
            }}
        }}

        // Real <ul> from either the "• a / • b" description string or an array of facts.
        // How well the dealt topic fits your tags / expertise (only while the admin has matching on)
        const MATCH_QUIPS = [
            [90, "#7cc19a", ["let him cook!", "this is your thesis, basically.", "home turf. Don't blow it."]],
            [70, "#9fd2b3", ["you've got this.", "right up your alley.", "talk like you wrote it."]],
            [45, "#e0c46c", ["could be worse.", "you've heard of it, probably.", "nod confidently."]],
            [20, "#e09a5c", ["tough luck!", "time to improvise.", "fake it till you make it."]],
            [0, "#e47f73", ["womp womp.", "godspeed.", "never heard of it? Neither have they, hopefully."]],
        ];
        function matchLine(pct) {{
            if (pct === null || pct === undefined) return '';
            const [, color, quips] = MATCH_QUIPS.find(([min]) => pct >= min);
            const quip = quips[(pct * 7 + (myPlayerName || '').length) % quips.length];
            return `<div class="statement-match"><b style="color:${{color}}">${{pct}}%</b> match, ${{quip}}</div>`;
        }}

        function factsList(d, redacted) {{
            const items = (Array.isArray(d) ? d : String(d || "").split("\\n"))
                .map(l => String(l).replace(/^\\s*•\\s*/, "").trim()).filter(Boolean);
            return items.length ? `<ul class="${{redacted ? "redacted" : ""}}">${{items.map(i => `<li>${{escapeHtml(i)}}</li>`).join("")}}</ul>` : "";
        }}

        // Animated open/close for the facts drawers (native <details> can't animate its height).
        function toggleDrawer(summary, ev) {{
            ev.preventDefault();
            const d = summary.parentElement, body = d.querySelector(".facts-content");
            if (!body || matchMedia("(prefers-reduced-motion: reduce)").matches) {{ d.open = !d.open; return; }}
            const opening = !d.open;
            if (opening) d.open = true;
            const h = body.scrollHeight + "px";
            const frames = opening ? [{{ height: "0px", opacity: 0 }}, {{ height: h, opacity: 1 }}] : [{{ height: h, opacity: 1 }}, {{ height: "0px", opacity: 0 }}];
            const a = body.animate(frames, {{ duration: 180, easing: "ease-out" }});
            if (!opening) a.onfinish = () => {{ d.open = false; }};
        }}

        // Identity: player id + session token. URL-controlled windows (test bench) use sessionStorage
        // so several players can share one browser.
        const idStore = isUrlControlled ? sessionStorage : localStorage;
        let myPlayerId = queryId || idStore.getItem("not_lying_player_id");
        let myPlayerName = queryName || idStore.getItem("not_lying_player_name");
        let myToken = isUrlControlled && queryName && queryName !== idStore.getItem("not_lying_player_name") ? null : idStore.getItem("not_lying_token");
        let joinMode = "new";

        function setJoinMode(mode) {{
            joinMode = mode;
            document.getElementById("tab-new").classList.toggle("active", mode === "new");
            document.getElementById("tab-back").classList.toggle("active", mode === "back");
            const perm = document.getElementById("permanent-input").checked;
            document.getElementById("permanent-row").style.display = mode === "new" ? "" : "none";
            document.getElementById("forgot-link").style.display = mode === "back" ? "" : "none";
            document.getElementById("pass-hint").innerText = (mode === "new" && perm) ? "(required, 4+ characters)" : (mode === "new" ? "(optional)" : "(if you set one)");
            document.getElementById("join-btn").innerText = mode === "new" ? "Enter Lobby" : "Log back in";
            document.getElementById("join-hint").innerText = mode === "back"
                ? "Lost your session? Enter the same name (and password) to pick up where you left off."
                : (perm ? "Saves your score and the topics you've heard, so future games won't repeat them."
                        : "A password lets you log back in if your phone loses the session. Temporary players are removed when the admin resets the game.");
            document.getElementById("join-error").innerText = "";
        }}

        window.addEventListener("DOMContentLoaded", () => {{
            setJoinMode("new");
            if (myPlayerName) document.getElementById("player-name-input").value = myPlayerName;
            if (myPlayerName && (myToken || isUrlControlled)) {{
                rejoin();
            }} else {{
                updateLoop();
            }}
        }});

        function saveIdentity(id, name, token) {{
            myPlayerId = id; myPlayerName = name; myToken = token;
            idStore.setItem("not_lying_player_id", id);
            idStore.setItem("not_lying_player_name", name);
            idStore.setItem("not_lying_token", token);
            document.title = `${{name}} - One of These People Is Not Lying`;
        }}

        async function sendJoin(body) {{
            const res = await fetch("/api/action", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify(Object.assign({{ action: "join" }}, body))
            }});
            const data = await res.json();
            if (!res.ok) throw Object.assign(new Error(data.error || "Could not join."), {{ needNew: !!data.need_new_password }});
            saveIdentity(data.joined_player_id, data.joined_player_name, data.token);
            showGameSection();
        }}

        async function rejoin() {{
            try {{
                await sendJoin({{ name: myPlayerName, token: myToken || "" }});
            }} catch (e) {{
                setJoinMode("back");
                document.getElementById("join-error").innerText = e.message;
                updateLoop();
            }}
        }}

        async function joinGame(ev) {{
            if (ev) ev.preventDefault();
            const name = document.getElementById("player-name-input").value.trim();
            const password = document.getElementById("player-pass-input").value;
            const permanent = joinMode === "new" && document.getElementById("permanent-input").checked;
            const new_password = document.getElementById("new-pass-input").value;
            if (!name) {{ document.getElementById("join-error").innerText = "Enter a name."; return; }}
            try {{
                await sendJoin({{ name, password, permanent, new_password, token: name === myPlayerName ? (myToken || "") : "" }});
            }} catch (e) {{
                document.getElementById("join-error").innerText = e.message;
                if (e.needNew) {{
                    document.getElementById("new-pass-row").style.display = "";
                    document.getElementById("new-pass-input").focus();
                }}
            }}
        }}

        async function forgotPassword() {{
            const name = document.getElementById("player-name-input").value.trim() || (prompt("Your account name:") || "").trim();
            if (!name) return;
            await fetch("/api/action", {{ method: "POST", headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ action: "request_reset", name }}) }});
            document.getElementById("player-name-input").value = name;
            document.getElementById("join-error").innerText = "";
            document.getElementById("join-hint").innerText = "The admin has been notified. Ask them for your temporary password, enter it above and log back in; you'll then choose a new one.";
        }}

        // Truth source links: the live page and the archived offline copy (PDFs open in the bundled pdf.js viewer).
        function srcLinks(s) {{
            const off = !s.archive ? "" : s.archive.endsWith(".pdf")
                ? `/archive/_pdfjs/web/viewer.html?file=${{encodeURIComponent("/archive/" + s.archive)}}#pagemode=none&zoom=page-width` : `/archive/${{encodeURIComponent(s.archive)}}`;
            return [escapeHtml(s.journal || s.publisher || ""), s.url ? `<a href="${{escapeHtml(s.url)}}" target="_blank" rel="noopener">Link</a>` : "",
                    off ? `<a href="${{off}}" target="_blank" rel="noopener">Offline copy</a>` : ""].filter(Boolean).join(" · ")
                + (s.institution || s.year ? `<br>${{escapeHtml([s.institution, s.year].filter(Boolean).join(" · "))}}` : "");
        }}
        function openReview() {{
            document.getElementById("review-score").value = 5; document.getElementById("review-out").value = "5/10";
            document.getElementById("review-text").value = ""; document.getElementById("review-status").textContent = ""; reviewCount();
            document.getElementById("review-dialog").showModal();
        }}
        function reviewCount() {{
            const n = document.getElementById("review-text").value.trim().split(/\\s+/).filter(Boolean).length;
            const el = document.getElementById("review-count");
            el.textContent = `${{n}}/100 words`; el.style.color = n > 100 ? "#e47f73" : "";
            document.getElementById("review-send").disabled = n > 100;
        }}
        async function submitReview(ev) {{
            ev.preventDefault();
            const btn = document.getElementById("review-send");
            btn.disabled = true;
            try {{
                const res = await fetch("/api/action", {{ method: "POST", headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ action: "review", player_id: myPlayerId, token: myToken,
                        score: +document.getElementById("review-score").value, text: document.getElementById("review-text").value }}) }});
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || "Couldn't send the review.");
                document.getElementById("review-status").textContent = "Thanks! Review saved.";
                setTimeout(() => document.getElementById("review-dialog").close(), 900);
            }} catch (e) {{
                document.getElementById("review-status").textContent = e.message;
            }} finally {{
                btn.disabled = false;
            }}
            return false;
        }}
        var lbMode = "all";
        function setLbMode(m) {{
            lbMode = m;
            document.getElementById("lb-all").setAttribute("aria-pressed", m === "all");
            document.getElementById("lb-game").setAttribute("aria-pressed", m === "game");
            document.getElementById("lb-cols").innerHTML = m === "all" ? "Wins &bull; Pts" : "Pts";
            m === "all" ? showLeaderboard() : renderGameBoard();
        }}
        function renderGameBoard() {{
            const st = (window.lastState && window.lastState.standings) || [];
            const html = st.length ? st.map((r, i) => `
                <div class="leader-row"${{r.id === myPlayerId ? ' style="background: rgba(233,228,216,0.1);"' : ''}}>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-weight: 800; width: 22px; text-align: center;">${{i + 1}}.</span>
                        <span style="font-weight: 700; color: #ece7dc;">${{escapeHtml(r.name)}}</span>
                    </div>
                    <span style="font-weight: 900; color: #d9a441;">${{r.score ?? 0}}</span>
                </div>`).join("") : '<div class="pack-count">No one is in this game yet.</div>';
            const rows = document.getElementById("leaderboard-rows");
            if (rows.dataset.h !== html) {{ rows.innerHTML = html; rows.dataset.h = html; }}
        }}
        async function showLeaderboard() {{
            document.getElementById("game-section").style.display = "none";
            document.getElementById("leaderboard-section").style.display = "block";
            if (lbMode === "game") return renderGameBoard();
            const rows = document.getElementById("leaderboard-rows");
            rows.dataset.h = "";
            try {{
                const lb = (await (await fetch("/api/leaderboard", {{ cache: "no-store" }})).json()).leaderboard || [];
                rows.innerHTML = lb.length ? lb.map((r, i) => `
                    <div class="leader-row"${{r.name.toLowerCase() === (myPlayerName || "").toLowerCase() ? ' style="background: rgba(233,228,216,0.1);"' : ''}}>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-weight: 800; width: 22px; text-align: center;">${{i + 1}}.</span>
                            <span><span style="font-weight: 700; color: #ece7dc;">${{escapeHtml(r.name)}}</span><br><span class="lb-sub">${{r.games}} games &bull; ${{r.rounds}} rounds</span></span>
                        </div>
                        <span style="font-weight: 900; color: #d9a441;">${{r.wins}} &bull; ${{r.points}}</span>
                    </div>`).join("") : '<div class="pack-count">No saved accounts yet.</div>';
            }} catch (e) {{
                rows.innerHTML = '<div class="pack-count">Could not load the leaderboard.</div>';
            }}
        }}
        function hideLeaderboard() {{
            document.getElementById("leaderboard-section").style.display = "none";
            document.getElementById("game-section").style.display = "block";
        }}

        function changeIdentity() {{
            if (confirm("Sign out on this device? You can log back in with your name (and password).")) {{
                ["not_lying_player_id", "not_lying_player_name", "not_lying_token"].forEach(k => idStore.removeItem(k));
                if (window.location.search) {{
                    window.location.href = window.location.pathname;
                }} else {{
                    location.reload();
                }}
            }}
        }}

        function showGameSection() {{
            document.getElementById("join-section").style.display = "none";
            document.getElementById("game-section").style.display = "block";
            document.getElementById("my-name-display").innerText = myPlayerName;
            updateLoop();
        }}

        async function updateLoop() {{
            try {{
                const queryStr = (myPlayerId && myToken) ? ("&player_id=" + encodeURIComponent(myPlayerId) + "&token=" + encodeURIComponent(myToken)) : "";
                const res = await fetch("/api/state?role=player" + queryStr + "&_t=" + Date.now(), {{ cache: "no-store" }});
                if (!res.ok) return;
                const state = await res.json();

                // If on Join Section, show live standings preview if game is active or round ended
                const joinPreview = document.getElementById("join-standings-preview");
                if (joinPreview) {{
                    if (state.standings && state.standings.length > 0 && (state.phase === "reveal" || state.round > 1)) {{
                        let previewRows = state.standings.map((s, idx) => {{
                            let medal = `${{idx + 1}}.`;
                            return `
                                <div class="leader-row">
                                    <div style="display: flex; align-items: center; gap: 8px;">
                                        <span style="font-weight: 800; width: 22px; text-align: center;">${{medal}}</span>
                                        <span style="font-weight: 700; color: #ece7dc;">${{escapeHtml(s.name || '')}}</span>
                                    </div>
                                    <span style="font-weight: 900; color: #d9a441;">${{s.score ?? 0}} pts</span>
                                </div>
                            `;
                        }}).join("");
                        joinPreview.style.display = "block";
                        joinPreview.innerHTML = `
                            <div class="leaderboard-card" style="margin-top: 14px;">
                                <div class="leaderboard-title">
                                    <span>Current Standings</span>
                                    <span style="font-size: 0.72rem; color: #d9a441; background: rgba(217,164,65, 0.2); padding: 2px 8px; border-radius: 8px;">Round ${{state.round}}</span>
                                </div>
                                ${{previewRows}}
                            </div>
                        `;
                    }} else {{
                        joinPreview.style.display = "none";
                    }}
                }}

                window.lastState = state;
                if (lbMode === "game" && document.getElementById("leaderboard-section").style.display !== "none") renderGameBoard();
                let me = state.my_info;
                const myRow = (state.players || []).find(p => p.id === myPlayerId);
                document.getElementById("my-score-display").innerText = myRow ? `${{myRow.score ?? 0}} pts` : "";
                const inGame = document.getElementById("game-section").style.display !== "none" || document.getElementById("leaderboard-section").style.display !== "none";
                if (!me && myToken && inGame) {{
                    // Removed by the admin, or the game was reset (temporary players are signed out).
                    myToken = null;
                    idStore.removeItem("not_lying_token");
                    document.getElementById("game-section").style.display = "none"; document.getElementById("leaderboard-section").style.display = "none";
                    document.getElementById("join-section").style.display = "";
                    setJoinMode("new");
                    document.getElementById("join-error").innerText = "You were signed out: the game ended or the admin removed you. Join again to start a new lobby.";
                    return;
                }}

                const phaseEl = document.getElementById("player-phase");
                if (phaseEl) {{
                    let phaseLabel = (state.phase || "lobby").toUpperCase();
                    if (state.phase === "setup") phaseLabel = `R${{state.round}} • Briefing`;
                    else if (state.phase === "questioning") phaseLabel = `R${{state.round}} • Questioning`;
                    else if (state.phase === "voting") phaseLabel = `R${{state.round}} • Accusation`;
                    else if (state.phase === "reveal") phaseLabel = `R${{state.round}} • Reveal`;
                    else if (state.phase === "lobby") phaseLabel = "Lobby";
                    phaseEl.innerText = phaseLabel;
                }}

                if (me) syncInterests(state, me);
                if (window.lastPhase !== undefined && window.lastPhase !== state.phase) phaseStamp(state.phase, state.round);
                window.lastPhase = state.phase;

                // Reset toggle memory if a new round begins
                if (window.lastTrackedRound !== undefined && window.lastTrackedRound !== state.round) {{
                    window.detailsFoldState = {{}};
                }}
                window.lastTrackedRound = state.round;

                const container = document.getElementById("role-container");
                if (!container) return;
                const vSec = document.getElementById("voting-section");

                // Capture current open/closed states from existing details elements in DOM
                container.querySelectorAll("details[id]").forEach(d => {{
                    window.detailsFoldState[d.id] = d.open;
                }});

                // If in Reveal phase: Display round results and current standings to ALL clients!
                if (state.phase === "reveal") {{
                    const res = state.last_results || {{}};
                    const tt = res.truth_teller || {{}};
                    const tts = (res.truth_tellers && res.truth_tellers.length > 0) ? res.truth_tellers : (tt ? [tt] : []);
                    const guesser = res.guesser || {{}};
                    const pickedList = (res.picked_players && res.picked_players.length > 0) ? res.picked_players : (res.picked_player ? [res.picked_player] : []);
                    const isCorrect = res.is_correct;
                    const ttNames = tts.map(t => escapeHtml(t.name)).join(" &amp; ");
                    const pickedNames = pickedList.map(p => escapeHtml(p.name)).join(" &amp; ") || "Nobody";

                    // Simple summary of the TV verdict: headline, one line, then each suspect's stamp.
                    const pickedIds = new Set(pickedList.map(p => p.id));
                    const headline = !pickedList.length ? ["No accusation.", "var(--paper-2)"]
                        : isCorrect ? ["Case closed.", "var(--truth)"] : ["The bluff held.", "var(--guesser)"];
                    const note = !pickedList.length ? `The truth came from <strong>${{ttNames || "the truth teller"}}</strong>.`
                        : isCorrect ? `The interrogators named <strong>${{pickedNames}}</strong>, and they were right.`
                        : `The interrogators accused <strong>${{pickedNames}}</strong>. The truth came from <strong>${{ttNames || "the truth teller"}}</strong>.`;
                    const myGain = ((state.standings || []).find(s => s.id === myPlayerId) || {{}}).pts_gained || 0;
                    const suspectRows = (state.players || []).filter(p => !p.is_guesser).map(p => {{
                        const truth = p.role === "truth_teller";
                        const isMe = p.id === myPlayerId;
                        return `
                            <div class="verdict-row${{isMe ? " me" : ""}}">
                                <span class="vr-name">${{escapeHtml(p.name)}}${{isMe ? " <small>(You)</small>" : ""}}${{pickedIds.has(p.id) ? ' <span class="vr-accused">Accused</span>' : ""}}</span>
                                <span class="stamp vr-stamp" style="color: ${{truth ? "var(--truth)" : "var(--liar)"}}">${{truth ? "Truth" : "Lie"}}</span>
                            </div>${{truth && p.source ? `<div class="statement-source vr-src">${{srcLinks(p.source)}}</div>` : ""}}`;
                    }}).join("");
                    let outcomeHtml = `
                        <div class="verdict-card">
                            <div class="eyebrow">Verdict</div>
                            <div class="verdict-title" style="color: ${{headline[1]}}">${{headline[0]}}</div>
                            <div class="verdict-note">${{note}}</div>
                            ${{myGain > 0 ? `<div class="verdict-gain">+${{myGain}} to you</div>` : ""}}
                            <div class="verdict-rows">${{suspectRows}}</div>
                        </div>
                    `;

                    // Standings list (clean mobile leaderboard)
                    let standingsRows = (state.standings || []).map((s, idx) => {{
                        const isMe = (s.id === myPlayerId || (s.name || "").toLowerCase() === (myPlayerName || "").toLowerCase());
                        let medal = `${{idx + 1}}.`;
                        let gainedTag = s.pts_gained > 0 
                            ? `<span style="background: rgba(94,166,126, 0.25); color: #7cc19a; font-weight: 800; font-size: 0.72rem; padding: 2px 6px; border-radius: 6px; margin-right: 6px;">+${{s.pts_gained}}</span>` 
                            : '';
                        let roleBadge = s.role === 'guesser' ? 'Guesser' : (s.role === 'truth_teller' ? 'Truth' : 'Liar');
                        return `
                            <div class="leader-row ${{isMe ? 'leader-row-me' : ''}}">
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    <span style="font-weight: 800; width: 22px; text-align: center;">${{medal}}</span>
                                    <div>
                                        <div style="font-weight: 700; color: ${{isMe ? '#e9e4d8' : '#ece7dc'}}; font-size: 0.88rem;">${{escapeHtml(s.name || '')}}${{isMe ? ' <span style="color: #d8d0bd; font-size: 0.72rem;">(You)</span>' : ''}}</div>
                                        <div style="font-size: 0.68rem; color: #a39b8c;">${{roleBadge}}</div>
                                    </div>
                                </div>
                                <div style="display: flex; align-items: center;">
                                    ${{gainedTag}}
                                    <span style="font-weight: 900; font-size: 0.95rem; color: #d9a441;">${{s.score ?? 0}} <span style="font-size: 0.68rem; font-weight: 600; color: #a39b8c;">pts</span></span>
                                </div>
                            </div>
                        `;
                    }}).join("");

                    let standingsHtml = `
                        <div class="leaderboard-card">
                            <div class="leaderboard-title">
                                <span>Current Standings</span>
                                <span style="font-size: 0.72rem; background: rgba(217,164,65, 0.2); color: #d9a441; padding: 2px 8px; border-radius: 8px;">Round ${{state.round}}</span>
                            </div>
                            ${{standingsRows}}
                            ${{readyHtml(state, "Ready for the next round")}}
                        </div>
                    `;

                    const revealFullHtml = outcomeHtml + standingsHtml;
                    if (container.dataset.renderedHtml !== revealFullHtml) {{
                        container.innerHTML = revealFullHtml;
                        container.dataset.renderedHtml = revealFullHtml;
                    }}
                    if (vSec) vSec.style.display = "none";
                    return;
                }}

                // If in Lobby, show clean waiting lobby card with roster & previous standings
                if (state.phase === "lobby") {{
                    let playersListHtml = (state.players || []).map(p => {{
                        const isMe = (p.id === myPlayerId || (p.name || "").toLowerCase() === (myPlayerName || "").toLowerCase());
                        return `<span class="badge" style="background: ${{isMe ? 'rgba(233,228,216,0.3)' : 'rgba(255,255,255,0.06)'}}; color: ${{isMe ? '#e9e4d8' : '#e2dccf'}}; padding: 5px 10px; margin: 2px; font-size: 0.82rem; border: 1px solid ${{isMe ? '#e9e4d8' : '#36312b'}}; border-radius: 12px;">${{escapeHtml(p.name)}}${{isMe ? ' (You)' : ''}}</span>`;
                    }}).join(" ");

                    let lobbyStandingsHtml = "";
                    if (state.round > 1 && state.standings && state.standings.length > 0) {{
                        let rows = state.standings.map((s, idx) => {{
                            const isMe = (s.id === myPlayerId || (s.name || "").toLowerCase() === (myPlayerName || "").toLowerCase());
                            let medal = `${{idx + 1}}.`;
                            return `
                                <div class="leader-row ${{isMe ? 'leader-row-me' : ''}}">
                                    <div style="display: flex; align-items: center; gap: 8px;">
                                        <span style="font-weight: 800; width: 22px; text-align: center;">${{medal}}</span>
                                        <span style="font-weight: 700; color: ${{isMe ? '#e9e4d8' : '#ece7dc'}};">${{escapeHtml(s.name)}}${{isMe ? ' (You)' : ''}}</span>
                                    </div>
                                    <span style="font-weight: 900; color: #d9a441;">${{s.score ?? 0}} pts</span>
                                </div>
                            `;
                        }}).join("");
                        lobbyStandingsHtml = `
                            <div class="leaderboard-card" style="margin-top: 14px;">
                                <div class="leaderboard-title">
                                    <span>Current Standings</span>
                                    <span style="font-size: 0.75rem; color: #a39b8c; font-weight: 600;">After Round ${{state.round - 1}}</span>
                                </div>
                                ${{rows}}
                            </div>
                        `;
                    }}

                    const lobbyFullHtml = `
                        <div style="background: rgba(233,228,216, 0.08); border: 1.5px dashed rgba(233,228,216, 0.35); border-radius: 14px; padding: 18px 12px; margin: 4px 0; text-align: center;">
                            <div style="font-size: 1.15rem; font-weight: 800; color: #e9e4d8; margin-bottom: 4px;">Game Lobby</div>
                            <div style="font-size: 0.82rem; color: #a39b8c; line-height: 1.4; margin-bottom: 12px;">
                                ${{state.can_ready ? "The round starts once everyone is ready." : "Waiting for more players."}}<br>
                                <span style="color: #c9bfa8;">Your secret role and topic will appear here!</span>
                            </div>
                            <div style="font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.6px; color: #a39b8c; font-weight: 700; margin-bottom: 6px;">
                                Connected Players (${{state.players ? state.players.length : 0}})
                            </div>
                            <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 2px;">
                                ${{playersListHtml}}
                            </div>
                            ${{readyHtml(state, "Ready to play")}}
                            ${{lobbyStandingsHtml}}
                        </div>
                    `;
                    if (container.dataset.renderedHtml !== lobbyFullHtml) {{
                        container.innerHTML = lobbyFullHtml;
                        container.dataset.renderedHtml = lobbyFullHtml;
                    }}
                    if (vSec) vSec.style.display = "none";
                    return;
                }}

                if (!me) {{
                    container.innerHTML = '<p style="color: #a39b8c; padding: 20px;">Waiting to sync with server...</p>';
                    return;
                }}

                const hideNow = !!(state.settings && state.settings.hide_facts) && ["questioning", "voting"].includes(state.phase);
                let cardHtml = "";
                if (me.is_guesser) {{
                    const isVoter = me.is_voting_guesser;
                    const voterName = me.voting_guesser_name || (isVoter ? me.name : (state.voting_guesser_name || state.guesser_name || "Lead Guesser"));
                    const fellowList = (me.fellow_guessers && me.fellow_guessers.length > 0) ? me.fellow_guessers.map(escapeHtml).join(", ") : "";
                    const truthCount = state.truth_teller_count || state.target_truth_teller_count || 1;

                    let teamBanner = "";
                    if (fellowList) {{
                        teamBanner = isVoter
                            ? `<div class="team-banner">Partner(s): <strong>${{fellowList}}</strong><div class="team-subtext">Deliberate together &bull; You cast the final accusation</div></div>`
                            : `<div class="team-banner">Lead Guesser: <strong>${{escapeHtml(voterName)}}</strong><div class="team-subtext">Interrogate together &bull; ${{escapeHtml(voterName)}} casts the final vote</div></div>`;
                    }}

                    let guesserAction = "";
                    if (isVoter) {{
                        if (state.phase === "setup") {{
                            guesserAction = `
                                <button class="btn" onclick="advanceGuesserStage()" style="margin-top: 8px; padding: 10px; font-size: 0.9rem;">
                                    <svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-play"/></svg> Start Questioning <svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-chevron-right"/></svg>
                                </button>
                            `;
                        }} else if (state.phase === "questioning") {{
                            guesserAction = `
                                <div style="margin-top: 8px; text-align: center;">
                                    <button class="btn" onclick="advanceGuesserStage()" style="padding: 11px; font-size: 0.92rem; ">
                                        Ready to Accuse <svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-chevron-right"/></svg>
                                    </button>
                                    <div style="font-size: 0.72rem; color: #a39b8c; margin-top: 4px;">Advance round to the accusation vote</div>
                                </div>
                            `;
                        }}
                    }} else {{
                        if (state.phase === "questioning") {{
                            guesserAction = `
                                <div style="margin-top: 8px; font-size: 0.76rem; color: #d3cbbb; text-align: center;">
                                    Deliberating with ${{escapeHtml(voterName)}}. They will advance to the vote when ready.
                                </div>
                            `;
                        }}
                    }}

                    const badgeTitle = isVoter ? (fellowList ? "Lead Guesser (Voter)" : "Guesser") : "Co-Guesser";
                    const goalText = isVoter
                        ? `Find the ${{truthCount > 1 ? `${{truthCount}} Truth Tellers` : 'Truth Teller'}} & cast your team's accusation`
                        : `Interrogate suspects & agree with ${{escapeHtml(voterName)}} on the truth`;

                    cardHtml = `
                        <div class="role-badge badge-guesser"><svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-search"/></svg> ${{badgeTitle}}</div>
                        ${{teamBanner}}
                        <div class="goal-pill">${{goalText}}</div>
                        ${{guesserAction}}
                    `;
                }} else if (me.is_truth_teller) {{
                    const categoryTag = me.category ? ` &bull; ${{escapeHtml(me.category)}}` : '';
                    const ttFactsOpen = (window.detailsFoldState['tt-facts-drawer'] !== false) ? 'open' : '';
                    cardHtml = `
                        <div class="role-badge badge-truth"><svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-check"/></svg> Truth Teller</div>
                        <div>
                            <span class="topic-pill">${{escapeHtml(me.topic || "Assigned Topic")}}${{categoryTag}}</span>
                        </div>
                        <div class="statement-card" style="border-left: 3px solid var(--truth-color);">
                            <button type="button" class="review-btn" onclick="openReview()" title="Rate this statement and its facts" aria-label="Leave a review"><svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-star"/></svg> Leave a review</button>
                            <div class="statement-label" style="color: var(--truth-color);">Your True Statement:</div>
                            <div class="statement-text">${{escapeHtml(me.statement || "No statement assigned")}}</div>
                            ${{me.detailed_description ? `
                                <details id="tt-facts-drawer" ${{ttFactsOpen}} class="facts-drawer" ontoggle="recordToggle(this)">
                                    <summary class="facts-summary" onclick="toggleDrawer(this, event)">Verified Facts${{hideNow ? " (redacted)" : ""}} <svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-chevron-right"/></svg></summary>
                                    <div class="facts-content">${{factsList(me.detailed_description, hideNow)}}</div>
                                </details>
                            ` : ''}}
                            ${{matchLine(me.match_pct)}}
                            ${{me.source ? (me.source.redacted ? `<div class="statement-source">Source redacted until the reveal</div>`
                                : `<div class="statement-source">${{srcLinks(me.source)}}</div>`) : ''}}
                        </div>
                    `;
                }} else {{
                    const categoryTag = me.category ? ` &bull; ${{escapeHtml(me.category)}}` : '';
                    cardHtml = `
                        <div class="role-badge badge-liar"><svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-fingerprint"/></svg> You Are Lying</div>
                        <div>
                            <span class="topic-pill">${{escapeHtml(me.topic || "Assigned Topic")}}${{categoryTag}}</span>
                        </div>
                        <div class="statement-card" style="border-left: 3px solid var(--liar-color);">
                            <button type="button" class="review-btn" onclick="openReview()" title="Rate this statement and its facts" aria-label="Leave a review"><svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-star"/></svg> Leave a review</button>
                            <div class="statement-label" style="color: var(--liar-color);">Your False Statement:</div>
                            <div class="statement-text">${{escapeHtml(me.statement || "No statement assigned")}}</div>
                            ${{(me.lie_facts && me.lie_facts.length) ? `
                                <details id="lie-facts-drawer" ${{(window.detailsFoldState['lie-facts-drawer'] !== false) ? 'open' : ''}} class="facts-drawer facts-liar" ontoggle="recordToggle(this)">
                                    <summary class="facts-summary" onclick="toggleDrawer(this, event)">Background Facts${{hideNow ? " (redacted)" : ""}} <svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-chevron-right"/></svg></summary>
                                    <div class="facts-content">${{factsList(me.lie_facts, hideNow)}}</div>
                                </details>
                            ` : ''}}
                            <div class="liar-tip">Bluff believable details and convince the guessers!</div>
                            ${{matchLine(me.match_pct)}}
                        </div>
                    `;
                }}

                // Suspects & Public Topics roster
                const suspects = (state.players || []).filter(p => !p.is_guesser);
                let suspectsHtml = `
                    <div class="roster-card">
                        <div class="roster-header">
                            <span>Suspects &amp; Topics</span>
                            <span style="font-size: 0.7rem; color: #9fd2b3; font-weight: 600;">1 Truth &bull; Rest Lies</span>
                        </div>
                `;
                suspects.forEach(s => {{
                    const isMe = s.id === myPlayerId || (s.name && myPlayerName && s.name.toLowerCase() === myPlayerName.toLowerCase());
                    suspectsHtml += `
                        <div class="roster-item" style="${{isMe ? 'border: 1px solid rgba(233,228,216,0.5); background: rgba(233,228,216,0.1);' : ''}}">
                            <span class="roster-name">${{escapeHtml(s.name)}}${{isMe ? ' <span style="color: #d8d0bd; font-size: 0.72rem;">(You)</span>' : ''}}</span>
                            <span class="roster-topic" title="${{escapeHtml(s.topic || 'Assigned Topic')}}">${{escapeHtml(s.topic || 'Assigned Topic')}}</span>
                        </div>
                    `;
                }});
                suspectsHtml += `</div>`;

                const activeFullHtml = cardHtml + suspectsHtml;
                if (container.dataset.renderedHtml !== activeFullHtml) {{
                    container.innerHTML = activeFullHtml;
                    container.dataset.renderedHtml = activeFullHtml;
                }}

                // Voting section: ONLY the designated voting guesser votes
                if (vSec) {{
                    if (state.phase === "voting") {{
                        vSec.style.display = "block";
                        const voterName = state.voting_guesser_name || state.guesser_name || "Lead Guesser";
                        const truthCount = state.truth_teller_count || state.target_truth_teller_count || 1;
                        if (me.is_guesser) {{
                            if (me.is_voting_guesser) {{
                                if (truthCount <= 1) {{
                                    let html = `
                                        <div style="font-size: 0.88rem; font-weight: 800; margin-bottom: 6px; color: #d9a441;">
                                            Select the Truth Teller:
                                        </div>
                                    `;
                                    (state.players || []).forEach(p => {{
                                        if (!p.is_guesser) {{
                                            const isSel = (Array.isArray(me.voted_for) ? me.voted_for.includes(p.id) : me.voted_for === p.id);
                                            const sel = isSel ? " selected" : "";
                                            html += `
                                                <button class="vote-btn${{sel}}" onclick="castMyVote('${{p.id}}')">
                                                    <span>${{escapeHtml(p.name)}}</span>
                                                    <span style="font-size: 0.75rem; color: #a39b8c; font-weight: 500;">${{p.topic ? escapeHtml(p.topic) : ''}}</span>
                                                </button>
                                            `;
                                        }}
                                    }});
                                    vSec.innerHTML = html;
                                }} else {{
                                    window.accusedSelections = window.accusedSelections || new Set();
                                    if (me.voted_for) {{
                                        const arr = Array.isArray(me.voted_for) ? me.voted_for : [me.voted_for];
                                        arr.forEach(id => window.accusedSelections.add(id));
                                    }}
                                    const selCount = window.accusedSelections.size;
                                    let html = `
                                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                            <span style="font-size: 0.88rem; font-weight: 800; color: #d9a441;">Select ALL ${{truthCount}} Truth Tellers:</span>
                                            <span style="font-size: 0.8rem; font-weight: 800; color: ${{selCount === truthCount ? '#7cc19a' : '#d9a441'}};">${{selCount}} / ${{truthCount}}</span>
                                        </div>
                                    `;
                                    (state.players || []).forEach(p => {{
                                        if (!p.is_guesser) {{
                                            const isChosen = window.accusedSelections.has(p.id);
                                            const selClass = isChosen ? " selected" : "";
                                            const checkIcon = isChosen ? "✓ " : "";
                                            html += `
                                                <button class="vote-btn${{selClass}}" onclick="toggleAccusedCandidate('${{p.id}}', ${{truthCount}})">
                                                    <div>
                                                        <span style="font-weight: 700;">${{checkIcon}}${{escapeHtml(p.name)}}</span>
                                                        <div style="font-size: 0.75rem; color: #a39b8c;">${{p.topic ? escapeHtml(p.topic) : ''}}</div>
                                                    </div>
                                                    ${{isChosen ? '<span style="font-size: 0.7rem; background: #d9a441; color: #000; font-weight: 900; padding: 2px 6px; border-radius: 8px;">ACCUSED</span>' : ''}}
                                                </button>
                                            `;
                                        }}
                                    }});
                                    const canSubmit = (selCount === truthCount);
                                    html += `
                                        <button id="btn-submit-multi-vote" class="btn" onclick="submitMultiVote(${{truthCount}})" style="width: 100%; margin-top: 8px; padding: 11px; font-size: 0.92rem; ${{canSubmit ? 'background: var(--guesser); border-color: var(--guesser); color: var(--paper-ink); font-weight: 800;' : 'opacity: 0.5; cursor: not-allowed;'}}" ${{canSubmit ? '' : 'disabled'}}>
                                            ${{canSubmit ? `Confirm Accusation (${{truthCount}}/${{truthCount}})` : `Select ${{truthCount - selCount}} more`}}
                                        </button>
                                    `;
                                    vSec.innerHTML = html;
                                }}
                            }} else {{
                                vSec.innerHTML = `
                                    <div style="background: rgba(233,228,216, 0.12); border: 1.5px solid #e9e4d8; border-radius: 12px; padding: 12px; text-align: center;">
                                        <div style="font-size: 0.95rem; font-weight: 800; color: #e9e4d8; margin-bottom: 2px;">Deliberating with ${{escapeHtml(voterName)}}</div>
                                        <div style="font-size: 0.78rem; color: #d3cbbb; line-height: 1.35;">
                                            Discuss and agree on who is telling the truth.<br>
                                            ${{escapeHtml(voterName)}} is submitting the vote.
                                        </div>
                                    </div>
                                `;
                            }}
                        }} else {{
                            vSec.innerHTML = `
                                <div style="background: rgba(0,0,0,0.25); padding: 12px; border-radius: 10px; border: 1px solid #36312b; text-align: center;">
                                    <div style="font-size: 0.88rem; font-weight: 700; color: #d9a441; margin-bottom: 2px;">Guesser Deliberation</div>
                                    <div style="font-size: 0.78rem; color: #d3cbbb; line-height: 1.35;">
                                        The guesser team is voting. Wait for the reveal!
                                    </div>
                                </div>
                            `;
                        }}
                    }} else {{
                        window.accusedSelections = new Set();
                        vSec.style.display = "none";
                    }}
                }}

            }} catch(e) {{
                console.error("Update loop error:", e);
            }}
        }}

        // Co-op style ready-up: once every player taps it, the server moves on by itself.
        function readyHtml(state, label) {{
            if (!state.can_ready) return `<div class="ready-wait">Need at least 3 players to start.</div>`;
            const total = (state.players || []).length, n = (state.ready_ids || []).length;
            const mine = (state.ready_ids || []).includes(myPlayerId);
            return `
                <button class="ready-btn${{mine ? " on" : ""}}" onclick="toggleReady()" aria-pressed="${{mine}}">
                    ${{mine ? "Ready ✓ <small>(tap to undo)</small>" : label}}
                </button>
                <div class="ready-wait">${{n}}/${{total}} ready${{n && n < total ? " (waiting on the rest)" : ""}}</div>`;
        }}

        // ---- Interests drawer ----
        let allTags = [], myTags = new Set(), savedExpertise = "", expDirty = false, intTabNow = null, matchMode = "off";
        function syncInterests(state, me) {{
            allTags = state.all_tags || [];
            tagOrder = me.tag_order || [];
            matchMode = (state.settings && state.settings.match_mode) || "off";
            const serverTags = me.tags || [];
            if (serverTags.join("|") !== [...myTags].join("|") && !window._tagSaving) {{ myTags = new Set(serverTags); }}
            savedExpertise = me.expertise || "";
            const exp = document.getElementById("exp-input");
            if (!expDirty && document.activeElement !== exp && exp.value !== savedExpertise) {{ exp.value = savedExpertise; expCount(); }}
            if (!intTabNow) intTab(matchMode === "expertise" ? "expertise" : "tags");
            ["tags", "expertise"].forEach(k => document.getElementById("it-" + k).classList.toggle("in-use", matchMode === k));
            const note = matchMode === "off" ? "Topic matching is off right now. Your picks apply when the host turns it on."
                : matchMode === "tags" ? "The host is matching topics by tags. You'll lean toward topics you know, not only those."
                : "The host is matching topics by expertise. You'll lean toward topics near what you wrote, not only those.";
            const modeEl = document.getElementById("int-mode");
            if (modeEl.textContent !== note) modeEl.textContent = note;
            const sum = matchMode === "expertise" ? (savedExpertise ? "expertise saved" : "nothing written yet")
                : (myTags.size ? [...myTags].join(", ") : "no tags yet");
            const sumEl = document.getElementById("int-sum");
            if (sumEl.textContent !== sum) sumEl.textContent = sum;
            renderTagChips();
        }}
        function intTab(k) {{
            intTabNow = k;
            ["tags", "expertise"].forEach(x => {{
                document.getElementById("it-" + x).classList.toggle("on", x === k);
                document.getElementById("it-" + x).setAttribute("aria-selected", x === k);
                document.getElementById("ip-" + x).hidden = x !== k;
            }});
        }}
        function renderTagChips() {{
            const q = document.getElementById("tag-search").value.trim().toLowerCase();
            const raw = document.getElementById("tag-search").value.trim().replace(/\\s+/g, " ").slice(0, 32);
            const known = new Map([...allTags, ...myTags].map(t => [t.toLowerCase(), t]));  // pack tags + your own
            const sort = document.getElementById("tag-sort").value;
            // Relevance: your tags A-Z, then the rest by closeness in meaning to your tags and expertise (server-ranked)
            const rank = new Map(tagOrder.map((t, i) => [t.toLowerCase(), i]));
            const list = [...known.values()].sort((a, b) => sort === "za" ? b.localeCompare(a)
                    : sort === "relevance" ? (myTags.has(b) - myTags.has(a)) || (myTags.has(a) ? a.localeCompare(b) : 0) || ((rank.get(a.toLowerCase()) ?? 1e9) - (rank.get(b.toLowerCase()) ?? 1e9)) || a.localeCompare(b)
                    : a.localeCompare(b))
                .filter(t => !q || t.toLowerCase().includes(q));
            const add = raw && !known.has(raw.toLowerCase())
                ? `<button type="button" class="tag-chip tag-add" data-tag="${{escapeHtml(raw)}}" onclick="addTag(this.dataset.tag)">+ Add "${{escapeHtml(raw)}}"</button>` : "";
            const html = add + list.map(t => `<button type="button" class="tag-chip" aria-pressed="${{myTags.has(t)}}" data-tag="${{escapeHtml(t)}}" onclick="toggleTag(this.dataset.tag)">${{escapeHtml(t)}}</button>`).join("");
            const box = document.getElementById("tag-chips");
            if (box.dataset.h !== html) {{ box.innerHTML = html; box.dataset.h = html; }}
        }}
        function addTag(t) {{
            if (myTags.size >= 40) return alert("That's the maximum of 40 tags.");
            myTags.add(t);
            document.getElementById("tag-search").value = "";
            renderTagChips();
            saveProfile(savedExpertise);
        }}
        function toggleTag(t) {{
            myTags.has(t) ? myTags.delete(t) : myTags.add(t);
            renderTagChips();
            saveProfile(savedExpertise);
        }}
        function expCount() {{
            document.getElementById("exp-count").textContent = document.getElementById("exp-input").value.length + "/600";
        }}
        function saveExpertise() {{
            const btn = document.getElementById("exp-save");
            saveProfile(document.getElementById("exp-input").value).then(ok => {{
                if (ok) {{ expDirty = false; btn.querySelector("use").setAttribute("href", "/static/icons.svg#i-check"); setTimeout(() => btn.querySelector("use").setAttribute("href", "/static/icons.svg#i-save"), 1500); }}
            }});
        }}
        let tagOrder = [];
        document.addEventListener("DOMContentLoaded", () => {{ document.getElementById("tag-sort").value = ({{auto: "relevance"}})[localStorage.getItem("tag_sort")] || localStorage.getItem("tag_sort") || "relevance"; }});
        async function autoTags() {{
            const note = document.getElementById("tag-note"), btn = document.getElementById("auto-tags-btn");
            btn.disabled = true; note.textContent = "Picking tags from your expertise...";
            try {{
                const res = await fetch("/api/action", {{ method: "POST", headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ action: "auto_tags", player_id: myPlayerId, token: myToken, expertise: document.getElementById("exp-input").value }}) }});
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || "Couldn't pick tags.");
                const fresh = data.tags.filter(t => ![...myTags].some(m => m.toLowerCase() === t.toLowerCase())).slice(0, Math.max(0, 40 - myTags.size));
                fresh.forEach(t => myTags.add(t));
                renderTagChips();
                if (await saveProfile(savedExpertise)) note.textContent = fresh.length ? `Added ${{fresh.length}}: ${{fresh.join(", ")}}.` : "No new tags: you already have them.";
            }} catch (e) {{
                note.textContent = e.message;
            }} finally {{
                btn.disabled = false;
            }}
        }}
        async function uploadResume(input) {{
            const file = input.files[0];
            input.value = "";
            if (!file) return;
            const note = document.getElementById("resume-note"), btn = document.getElementById("resume-btn");
            if (file.size > 5 * 1024 * 1024) {{ note.textContent = "That PDF is over 5 MB."; return; }}
            btn.disabled = true;
            note.textContent = "Reading your resume. This can take up to a minute.";
            try {{
                const pdf = await new Promise((ok, bad) => {{ const r = new FileReader(); r.onload = () => ok(r.result.split(",")[1]); r.onerror = bad; r.readAsDataURL(file); }});
                const res = await fetch("/api/action", {{ method: "POST", headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ action: "parse_resume", player_id: myPlayerId, token: myToken, pdf }}) }});
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || "Could not read that resume.");
                const d = data.draft;
                document.getElementById("exp-input").value = d.expertise; expCount();
                d.tags.slice(0, Math.max(0, 40 - myTags.size)).forEach(t => myTags.add(t));
                if (await saveProfile(d.expertise)) {{ expDirty = false; note.textContent = `Done: expertise written and ${{d.tags.length}} tags added. Edit anything you like.`; }}
            }} catch (e) {{
                note.textContent = e.message;
            }} finally {{
                btn.disabled = false;
            }}
        }}
        async function saveProfile(expertise) {{
            window._tagSaving = true;
            try {{
                const res = await fetch("/api/action", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ action: "set_profile", player_id: myPlayerId, token: myToken, tags: [...myTags], expertise }})
                }});
                if (!res.ok) {{ alert((await res.json()).error || "Could not save your interests."); return false; }}
                await updateLoop();
                return true;
            }} catch (e) {{
                alert("Error: " + e);
                return false;
            }} finally {{
                window._tagSaving = false;
            }}
        }}

        const STAMPS = {{ lobby: ["Lobby", "#a39b8c"], setup: ["Briefing", "#e9e4d8"], questioning: ["Questioning", "#d9a441"],
                          voting: ["Accusation", "#e0675a"], reveal: ["Verdict", "#5ea67e"] }};
        function phaseStamp(phase, round) {{
            const [label, color] = STAMPS[phase] || [phase, "#e9e4d8"];
            const el = document.getElementById("phase-stamp"), card = document.getElementById("game-section");
            el.querySelector("b").textContent = label;
            el.querySelector("small").textContent = phase === "lobby" ? "" : "ROUND " + round;
            el.style.setProperty("--stamp", color);
            el.classList.remove("go"); card.classList.remove("phase-in"); void el.offsetWidth;
            el.classList.add("go"); card.classList.add("phase-in");
        }}

        async function toggleReady() {{
            try {{
                const res = await fetch("/api/action", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ action: "toggle_ready", player_id: myPlayerId, token: myToken }})
                }});
                if (!res.ok) alert((await res.json()).error || "Could not ready up.");
                updateLoop();
            }} catch (e) {{
                alert("Error: " + e);
            }}
        }}

        async function advanceGuesserStage() {{
            try {{
                const res = await fetch("/api/action", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ action: "guesser_advance", player_id: myPlayerId, token: myToken }})
                }});
                if (res.ok) {{
                    updateLoop();
                }} else {{
                    const data = await res.json();
                    alert(data.error || "Could not advance stage.");
                }}
            }} catch (e) {{
                alert("Error advancing stage: " + e);
            }}
        }}

        function toggleAccusedCandidate(pid, maxCount) {{
            window.accusedSelections = window.accusedSelections || new Set();
            if (window.accusedSelections.has(pid)) {{
                window.accusedSelections.delete(pid);
            }} else {{
                if (window.accusedSelections.size >= maxCount) {{
                    alert("You can only select " + maxCount + " suspects.");
                    return;
                }}
                window.accusedSelections.add(pid);
            }}
            updateLoop();
        }}

        async function submitMultiVote(expectedCount) {{
            window.accusedSelections = window.accusedSelections || new Set();
            if (window.accusedSelections.size !== expectedCount) {{
                alert("Please select exactly " + expectedCount + " suspects before submitting.");
                return;
            }}
            const targetIds = Array.from(window.accusedSelections);
            try {{
                const res = await fetch("/api/action", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ action: "cast_vote", voter_id: myPlayerId, target_ids: targetIds, token: myToken }})
                }});
                if (res.ok) {{
                    window.accusedSelections.clear();
                    updateLoop();
                }} else {{
                    const data = await res.json();
                    alert(data.error || "Could not cast vote.");
                }}
            }} catch (e) {{
                alert("Error casting vote: " + e);
            }}
        }}

        async function castMyVote(targetId) {{
            try {{
                const res = await fetch("/api/action", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ action: "cast_vote", voter_id: myPlayerId, target_id: targetId, target_ids: [targetId], token: myToken }})
                }});
                if (res.ok) {{
                    updateLoop();
                }} else {{
                    const data = await res.json();
                    alert(data.error || "Could not cast vote.");
                }}
            }} catch (e) {{
                alert("Error casting vote: " + e);
            }}
        }}

        setInterval(updateLoop, 1000);
    </script>
</body>
</html>
"""

def get_display_html(port: int) -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Player Display - One of These People Is Not Lying</title>
    <link rel="stylesheet" href="/static/app.css">
    <style>
        html { font-size: clamp(14px, 1.04vw, 24px); }
        body { min-height: 100vh; overflow-x: hidden; }
        .tv { position: relative; z-index: 1; display: flex; flex-direction: column; gap: 1.6rem; min-height: 100vh; padding: 2rem 3rem 2.4rem; }
        .tv.shake { animation: shake 0.42s cubic-bezier(0.36, 0.07, 0.19, 0.97); }
        @keyframes shake { 15% { transform: translate(-6px, 4px); } 30% { transform: translate(5px, -3px); } 45% { transform: translate(-3px, 2px); } 60% { transform: translate(2px, -1px); } 100% { transform: none; } }
        .tv-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 2rem; border-bottom: 1px solid var(--line); padding-bottom: 1.1rem; }
        .tv-head h1 { margin: 0.2rem 0 0; font-size: 2.4rem; line-height: 1.05; position: relative; z-index: 3; }
        .phases { display: flex; gap: 0.4rem; margin: 0; padding: 0; list-style: none; flex-wrap: wrap; justify-content: flex-end; }
        .phases li { font: 600 0.72rem var(--font-mono); letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted);
                     padding: 0.45rem 0.8rem; border: 1px solid var(--line-soft); border-radius: 999px; transition: background 0.4s, color 0.4s; }
        .phases li.done { color: var(--paper-2); border-color: var(--line); }
        .phases li.now { color: var(--paper-ink); background: var(--paper); border-color: var(--paper); }

        /* Brief (interrogation) and verdict (reveal) share one slot and cross-fade. */
        .head-swap { display: grid; align-items: center; min-height: 7.4rem; }  /* fixed height: files never shift when the verdict swaps in */
        .head-swap > * { grid-area: 1 / 1; transition: opacity 0.6s ease, transform 0.6s ease; }
        .brief { display: flex; align-items: center; gap: 1.4rem; flex-wrap: wrap; }
        .interrogator { display: flex; align-items: center; gap: 0.9rem; padding: 0.8rem 1.2rem; border: 1px solid rgba(217,164,65,0.45);
                        border-radius: var(--radius); background: rgba(217,164,65,0.08); }
        .interrogator .icon { width: 1.8rem; height: 1.8rem; color: var(--guesser); }
        .interrogator b { display: block; font: 650 1.7rem var(--font-display); color: var(--guesser); line-height: 1.1; }
        .interrogator small { color: var(--paper-2); font-size: 0.85rem; }
        .hint { font-size: 1.15rem; color: var(--paper-2); max-width: 46rem; line-height: 1.45; }
        .hint strong { color: var(--text); }
        .verdict { opacity: 0; transform: translateY(10px); pointer-events: none; }
        .verdict h2 { margin: 0; font-size: 3rem; line-height: 1.05; }
        .verdict p { margin: 0.5rem 0 0; font-size: 1.2rem; color: var(--paper-2); }
        .verdict p strong { color: var(--text); }
        body.revealed .brief { opacity: 0; transform: translateY(-10px); pointer-events: none; }
        body.revealed .verdict { opacity: 1; transform: none; }

        /* Standings column slides open on reveal. */
        .case { display: grid; grid-template-columns: 1fr 0rem; column-gap: 0rem; align-items: start;
                transition: grid-template-columns 0.9s ease, column-gap 0.9s ease; }
        body.revealed .case { grid-template-columns: 1fr 22rem; column-gap: 2rem; }
        .standings { overflow: hidden; opacity: 0; transition: opacity 0.6s ease 0.4s; }
        body.revealed .standings { opacity: 1; }
        .standings-in { width: 22rem; background: var(--ink-2); border: 1px solid var(--line); border-radius: var(--radius); padding: 1.1rem 1.2rem; }
        .standings h3 { margin: 0 0 0.8rem; font-size: 1.3rem; }
        .row { display: grid; grid-template-columns: 2rem 1fr auto auto; gap: 0.7rem; align-items: center; padding: 0.55rem 0; border-top: 1px solid var(--line-soft); }
        .row .rk { font: 600 0.9rem var(--font-mono); color: var(--muted); }
        .row .nm { font-weight: 650; font-size: 1.1rem; overflow-wrap: anywhere; }
        .row .nm small { display: block; font: 600 0.62rem var(--font-mono); letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted); }
        .row .gain { font: 600 0.85rem var(--font-mono); color: var(--truth); }
        .row .gain.zero { color: var(--muted); }
        .row .pts { font: 700 1.4rem var(--font-display); color: var(--guesser); min-width: 2.5rem; text-align: right; }
        .row:first-of-type .rk { color: var(--guesser); }

        /* Suspect files persist from briefing to reveal; only their classes change. */
        .files { display: grid; grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr)); gap: 2rem 1.6rem; align-content: start; align-items: start; padding-top: 0.9rem; }
        .file { position: relative; padding: 1.3rem 1.4rem 1.2rem; min-height: 12rem; display: flex; flex-direction: column; gap: 0.5rem;
                animation: file-in 0.5s ease backwards;
                transition: filter 1.2s ease, transform 0.5s cubic-bezier(0.3, 1.4, 0.5, 1), outline-color 0.5s ease; outline: 3px solid transparent; outline-offset: 5px; }
        .file::before { content: ""; position: absolute; top: -0.7rem; left: 1.2rem; width: 6rem; height: 0.9rem;
                        background: var(--paper-2); border-radius: 4px 4px 0 0; }
        .file .no { font: 600 0.72rem var(--font-mono); letter-spacing: 0.16em; color: #6d6455; }
        .file .name { font: 700 2.3rem var(--font-display); line-height: 1.05; overflow-wrap: anywhere; }
        .file .subject { margin-top: auto; padding-top: 0.6rem; border-top: 1px dashed rgba(36,32,27,0.3); font: 600 1.05rem var(--font-mono); line-height: 1.35; }
        .file .subject span { display: block; font-size: 0.66rem; letter-spacing: 0.18em; color: #6d6455; font-weight: 600; }
        .file .score { position: absolute; top: 1.1rem; right: 1.2rem; font: 600 0.8rem var(--font-mono); color: #6d6455; }
        .file.selected { transform: scale(1.045); outline-color: var(--guesser); z-index: 2; }
        .dossier { display: grid; grid-template-rows: 0fr; transition: grid-template-rows 0.8s ease; }
        .dossier-in { min-height: 0; overflow: hidden; opacity: 0; transition: opacity 0.6s ease 0.2s; }
        .file.open .dossier { grid-template-rows: 1fr; }
        .file.open .dossier-in { opacity: 1; }
        .file .src { font: 600 0.72rem var(--font-mono); letter-spacing: 0.08em; color: #2f7a52; padding-top: 0.4rem; }
        .file .src:empty { display: none; }
        .file .said { font: 400 0.98rem/1.45 var(--font-mono); padding-top: 0.5rem; text-align: justify; hyphens: auto; }
        /* Every phase must fit one 16:9 screen: fit() shrinks the stage with zoom; .fitting lets it measure the end state instantly. */
        body.fitting, body.fitting * { transition: none !important; }
        .file .pad { height: 2.6rem; }
        .file .stamp { position: absolute; right: 1rem; bottom: 1rem; font-size: 1.15rem; background: rgba(233,228,216,0.85); opacity: 0; }
        .file.stamped .stamp { animation: stamp-in 0.45s cubic-bezier(0.2, 1.6, 0.4, 1) both; }
        .file.truth .stamp { color: #2f7a52; }
        .file.lie .stamp { color: var(--red); }
        @keyframes file-in { from { opacity: 0; transform: translateY(10px); } }

        .lobby { display: grid; grid-template-columns: minmax(18rem, 26rem) 1fr; gap: 3rem; align-items: start; }
        .qr-card { padding: 1.6rem; text-align: center; }
        .qr-card img { width: 100%; max-width: 20rem; aspect-ratio: 1; mix-blend-mode: multiply; }
        .qr-card .url { margin-top: 0.9rem; font: 600 1.15rem var(--font-mono); overflow-wrap: anywhere; }
        .room h2 { margin: 0 0 1rem; font-size: 2rem; }
        .chips { display: flex; flex-wrap: wrap; gap: 0.7rem; }
        .chip { padding: 0.6rem 1.1rem; border: 1px solid var(--line); border-radius: 999px; background: var(--ink-2); font-size: 1.15rem; font-weight: 600; animation: file-in 0.4s ease backwards; }
        .empty { color: var(--muted); font-size: 1.1rem; }

        /* ---- TV atmosphere: layers sit between the background (z 0) and .tv (z 1); light and frame go over it ---- */
        .fx-tv { --grain: 0.12; }
        .fx-layer { position: fixed; pointer-events: none; z-index: 0; }
        #vignette { inset: 0; z-index: 2; transition: opacity 1s ease;
                    background: radial-gradient(ellipse 80% 75% at 50% 45%, transparent 55%, rgba(0,0,0,0.5) 100%);
                    animation: room-flicker 9s steps(1) infinite; }
        @keyframes room-flicker { 0%, 100% { opacity: 1; } 41% { opacity: 0.93; } 42% { opacity: 1; } 77% { opacity: 0.96; } 78% { opacity: 1; } }
        #dark { inset: 0; background: rgba(0,0,0,0.3); opacity: 0; transition: opacity 1.2s ease, background 1.2s ease; }

        /* Questioning: a ceiling lamp drops in on its cord and swings; accusation pulls it back up. */
        /* inside .tv so it can sit over the header rule (z 2) but under the title (z 3) */
        #lamp { left: 50%; top: -2rem; width: 0; height: 0; z-index: 2; }
        #lamp .drop { transform: translateY(-80rem); transition: transform 0.9s cubic-bezier(0.55, 0, 0.85, 0.3); }
        body[data-phase="questioning"] #lamp .drop { transform: none; transition: transform 1.6s cubic-bezier(0.25, 1.3, 0.45, 1); }
        #lamp .arm { position: absolute; left: 0; top: 0; transform-origin: 0 0; animation: swing 3.2s ease-in-out infinite alternate; }
        #lamp .cord { position: absolute; left: -1px; top: 0; width: 2px; height: 7rem; background: #4a4238; }
        #lamp .shade { position: absolute; left: -2.6rem; top: 7rem; width: 5.2rem; height: 2.2rem; border-radius: 2.6rem 2.6rem 0.4rem 0.4rem;
                       background: linear-gradient(#2c2823, #15130f); box-shadow: 0 0.9rem 1.6rem rgba(255,226,160,0.35); }
        #lamp .cone { position: absolute; left: -36rem; top: 9rem; width: 72rem; height: 62rem;
                      background: radial-gradient(ellipse 50% 100% at 50% 0%, rgba(255,232,180,0.2), rgba(255,232,180,0.06) 55%, transparent 75%);
                      clip-path: polygon(46.4% 0, 53.6% 0, 100% 100%, 0 100%); }
        @keyframes swing { from { transform: rotate(-17deg); } to { transform: rotate(17deg); } }

        /* Accusation: a searching spotlight with crosshairs, red frame pulsing like a heartbeat. */
        #beam { left: 50%; top: 50%; width: 0; height: 0; z-index: 2; opacity: 0;
                transition: left 1.3s cubic-bezier(0.5, 0, 0.2, 1), top 1.3s cubic-bezier(0.5, 0, 0.2, 1), opacity 0.8s ease; }
        #beam .glow { position: absolute; width: 40rem; height: 40rem; left: -20rem; top: -20rem; mix-blend-mode: screen;
                      background: radial-gradient(circle, rgba(255,236,215,0.2) 0%, rgba(255,236,215,0.07) 35%, transparent 62%); }
        #beam .reticle { position: absolute; width: 11rem; height: 11rem; left: -5.5rem; top: -5.5rem; border-radius: 50%;
                         border: 2px solid rgba(224,103,90,0.85); box-shadow: 0 0 1.2rem rgba(224,103,90,0.35);
                         animation: reticle 6s linear infinite; }
        #beam .reticle::before, #beam .reticle::after { content: ""; position: absolute; left: 50%; top: 50%; background:
                         linear-gradient(90deg, rgba(224,103,90,0.85) 0 36%, transparent 36% 64%, rgba(224,103,90,0.85) 64%); }
        #beam .reticle::before { width: 15rem; height: 2px; margin: -1px 0 0 -7.5rem; }
        #beam .reticle::after { width: 2px; height: 15rem; margin: -7.5rem 0 0 -1px;
                         background: linear-gradient(180deg, rgba(224,103,90,0.85) 0 36%, transparent 36% 64%, rgba(224,103,90,0.85) 64%); }
        @keyframes reticle { to { transform: rotate(360deg); } }
        #frame { inset: 0; z-index: 2; opacity: 0; transition: opacity 0.8s ease;
                 box-shadow: inset 0 0 0 0.35rem rgba(179,65,47,0.85), inset 0 0 9rem rgba(179,65,47,0.32); }
        @keyframes heartbeat { 0%, 100% { opacity: 0.55; } 12% { opacity: 1; } 24% { opacity: 0.6; } 36% { opacity: 0.95; } 55% { opacity: 0.55; } }

        body[data-phase="questioning"] #dark { opacity: 1; }
        body[data-phase="questioning"] #vignette { background: radial-gradient(ellipse 75% 70% at 50% 45%, transparent 45%, rgba(0,0,0,0.68) 100%); }
        body[data-phase="questioning"] .files .file { filter: brightness(0.86); }
        body[data-phase="voting"] #dark { opacity: 1; background: rgba(0,0,0,0.45); }
        body[data-phase="voting"] #vignette { background: radial-gradient(ellipse 72% 65% at 50% 45%, transparent 40%, rgba(25,0,0,0.75) 100%); }
        body[data-phase="voting"] #beam { opacity: 1; }
        body[data-phase="voting"] #frame { opacity: 1; animation: heartbeat var(--beat, 1.1s) ease-in-out infinite; }
        body[data-phase="voting"] .files .file { filter: brightness(0.74); }
        body[data-phase="voting"] .files .file.targeted { filter: brightness(1.05); }

        /* Gavel strike between accusation and reveal. */
        #gavel { inset: 0; z-index: 5; display: grid; place-items: center; opacity: 0; background: rgba(0,0,0,0.55); }
        #gavel.hit { animation: gavel-fade 1.5s ease both; }
        #gavel .rig { position: relative; width: 30rem; height: 14.3rem; }
        #gavel .block { position: absolute; left: 0.5rem; bottom: 0; width: 12rem; height: 3rem; border-radius: 0.6rem;
                        background: linear-gradient(#6b4a2c, #3d2915); box-shadow: 0 0.6rem 1.5rem rgba(0,0,0,0.6); }
        #gavel .swing { position: absolute; left: 6rem; top: 6rem; width: 22rem; height: 1.5rem; transform-origin: 100% 50%; transform: rotate(55deg); }
        #gavel.hit .swing { animation: gavel-swing 1.5s both; }
        #gavel .handle { position: absolute; inset: 0; border-radius: 0.75rem; background: linear-gradient(#8a6038, #5a3c20); }
        #gavel .head { position: absolute; left: -1.5rem; top: -3.75rem; width: 4rem; height: 9rem; border-radius: 0.7rem;
                       background: linear-gradient(90deg, #5a3c20, #8a6038 45%, #5a3c20),
                                   linear-gradient(transparent 18%, #c9a227 18% 24%, transparent 24% 76%, #c9a227 76% 82%, transparent 82%);
                       background-blend-mode: overlay; }
        #gavel .ring { position: absolute; left: 6.5rem; top: 11.3rem; width: 0; height: 0; border-radius: 50%;
                       box-shadow: 0 0 0 0 rgba(233,228,216,0.7); }
        #gavel.hit .ring { animation: gavel-ring 1.5s ease-out both; }
        @keyframes gavel-fade { 0% { opacity: 0; } 12% { opacity: 1; } 80% { opacity: 1; } 100% { opacity: 0; } }
        @keyframes gavel-swing { 0%, 15% { transform: rotate(55deg); animation-timing-function: cubic-bezier(0.6, 0, 1, 1); }
                                 40% { transform: rotate(-1deg); } 47% { transform: rotate(9deg); } 55%, 100% { transform: rotate(0); } }
        @keyframes gavel-ring { 0%, 39% { box-shadow: 0 0 0 0 rgba(233,228,216,0.7); }
                                70%, 100% { box-shadow: 0 0 0 14rem rgba(233,228,216,0); } }
    </style>
</head>
<body class="theme-noir fx-grain fx-spotlight fx-tv">
    <div class="fx-layer" id="dark"></div>
    <div class="fx-layer" id="beam"><div class="glow"></div><div class="reticle"></div></div>
    <div class="fx-layer" id="vignette"></div>
    <div class="fx-layer" id="frame"></div>
    <div class="fx-layer" id="gavel"><div class="rig"><div class="block"></div><div class="ring"></div><div class="swing"><div class="handle"></div><div class="head"></div></div></div></div>
    <div class="tv">
        <div class="fx-layer" id="lamp"><div class="drop"><div class="arm"><div class="cord"></div><div class="shade"></div><div class="cone"></div></div></div></div>
        <header class="tv-head">
            <div>
                <div class="eyebrow" id="case-no">Case file &middot; Round 1</div>
                <h1>One of These People Is Not Lying</h1>
            </div>
            <ol class="phases" id="phases"></ol>
        </header>
        <main id="stage"></main>
    </div>

    <script>
        const PHASES = [["lobby", "Lobby"], ["setup", "Briefing"], ["questioning", "Questioning"], ["voting", "Accusation"], ["reveal", "Reveal"]];
        const ICON = (n) => `<svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-${n}"/></svg>`;
        const $ = (id) => document.getElementById(id);
        const body = document.body;
        let mode = "", prevPhase = null, phaseSince = Date.now(), timers = [];

        function esc(str) {
            if (str === null || str === undefined) return "";
            return String(str).replace(/[&<>"']/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[m]));
        }
        const pad = (n) => String(n).padStart(2, "0");
        // Write only on change, so polling never restarts animations or transitions.
        const setHTML = (el, html) => { if (el.dataset.h !== html) { el.innerHTML = html; el.dataset.h = html; } };
        const setText = (el, t) => { if (el.textContent !== t) el.textContent = t; };

        function lobby(state) {
            const url = location.origin + "/join";
            const people = state.players || [];
            return `
                <section class="lobby">
                    <div class="qr-card paper">
                        <div class="eyebrow" style="color:#6d6455">Scan to join</div>
                        <img src="/api/qr.svg?url=${encodeURIComponent(url)}" alt="QR code for ${esc(url)}">
                        <div class="url">${esc(url.replace(/^https?:\\/\\//, ""))}</div>
                    </div>
                    <div class="room">
                        <div class="eyebrow">${people.length} in the room</div>
                        <h2>Waiting for the investigation to begin</h2>
                        <div class="chips">${people.length ? people.map(p => `<span class="chip">${esc(p.name)}</span>`).join("") : `<span class="empty">Nobody yet. Scan the code to join.</span>`}</div>
                    </div>
                </section>`;
        }

        const CASE = `
            <section class="head-swap">
                <div class="brief" id="brief"></div>
                <div class="verdict"><div class="eyebrow">Verdict</div><h2 id="verdict-h"></h2><p id="verdict-p"></p></div>
            </section>
            <section class="case">
                <div class="files" id="files"></div>
                <aside class="standings"><div class="standings-in"><h3>Standings</h3><div id="rows"></div></div></aside>
            </section>`;
        const CARD = `<div class="no"></div><div class="score"></div><div class="name"></div>
            <div class="subject"><span>SUBJECT</span><b class="topic"></b></div>
            <div class="dossier"><div class="dossier-in"><div class="said"></div><div class="src"></div><div class="pad"></div></div></div>
            <span class="stamp"></span>`;

        function brief(state) {
            const guessers = (state.players || []).filter(p => p.is_guesser);
            const lead = guessers.find(p => p.is_voting_guesser) || guessers[0];
            const others = guessers.filter(p => lead && p.id !== lead.id);
            const hints = {
                setup: "Suspects, read your statement and get your story straight. <strong>Questioning starts soon.</strong>",
                questioning: "Question every suspect about their subject. <strong>Only one of them is telling the truth.</strong>",
                voting: "Questioning is over. <strong>The interrogator is making an accusation.</strong>"
            };
            if (state.phase === "reveal") return;  // keep the last brief underneath the verdict
            setHTML($("brief"), `
                <div class="interrogator">${ICON("search")}
                    <div><small>${guessers.length > 1 ? "Lead interrogator" : "Interrogator"}</small><b>${esc(lead ? lead.name : "Unassigned")}</b>
                    ${others.length ? `<small>with ${others.map(o => esc(o.name)).join(", ")}</small>` : ""}</div>
                </div>
                <div class="hint">${hints[state.phase] || ""}</div>`);
        }

        function files(state, picked) {
            const box = $("files"), reveal = state.phase === "reveal";
            const suspects = (state.players || []).filter(p => !p.is_guesser);
            const els = suspects.map((p, i) => {
                let el = $("f-" + p.id);
                if (!el) {
                    el = document.createElement("article");
                    el.className = "file paper"; el.id = "f-" + p.id; el.dataset.id = p.id;
                    el.style.animationDelay = (i * 60) + "ms"; el.innerHTML = CARD;
                }
                return el;
            });
            [...box.children].forEach(c => { if (!els.includes(c)) c.remove(); });
            els.forEach((el, i) => { if (box.children[i] !== el) box.insertBefore(el, box.children[i] || null); });
            suspects.forEach((p, i) => {
                const el = els[i], truth = p.role === "truth_teller";
                setText(el.querySelector(".no"), `SUSPECT ${pad(i + 1)}` + (reveal && picked.has(p.id) ? " · ACCUSED" : ""));
                setText(el.querySelector(".score"), `${p.score} pts`);
                setText(el.querySelector(".name"), p.name);
                setText(el.querySelector(".topic"), p.topic || "Assigned at round start");
                setText(el.querySelector(".said"), reveal ? (p.statement || "") : "");
                setText(el.querySelector(".src"), reveal && truth && p.source ? `Source: ${p.source.journal} ${p.source.year}` : "");
                setText(el.querySelector(".stamp"), truth ? "Truth" : "Lie");
                el.classList.toggle("truth", reveal && truth);
                el.classList.toggle("lie", reveal && !truth);
            });
        }

        function verdict(state, picked) {
            const r = state.last_results || {};
            const tts = (r.truth_tellers && r.truth_tellers.length) ? r.truth_tellers : (r.truth_teller ? [r.truth_teller] : []);
            const pk = (r.picked_players && r.picked_players.length) ? r.picked_players : (r.picked_player ? [r.picked_player] : []);
            const ttNames = tts.map(t => esc(t.name)).join(" &amp; ") || "the truth teller";
            const pickedNames = pk.map(p => esc(p.name)).join(" &amp; ");
            const h = $("verdict-h");
            setText(h, !pk.length ? "No accusation." : r.is_correct ? "Case closed." : "The bluff held.");
            h.style.color = !pk.length ? "var(--paper-2)" : r.is_correct ? "var(--truth)" : "var(--guesser)";
            setHTML($("verdict-p"), !pk.length ? `No accusation was made. The truth came from <strong>${ttNames}</strong>.`
                : r.is_correct ? `The interrogators named <strong>${pickedNames}</strong>, and they were right.`
                : `The interrogators accused <strong>${pickedNames}</strong>. The truth came from <strong>${ttNames}</strong>.`);
            setHTML($("rows"), (state.standings || []).map((s, i) => `
                <div class="row">
                    <span class="rk">${pad(i + 1)}</span>
                    <span class="nm">${esc(s.name)}<small>${s.role === "guesser" ? "Interrogator" : s.role === "truth_teller" ? "Truth teller" : "Liar"}</small></span>
                    <span class="gain ${s.pts_gained > 0 ? "" : "zero"}">+${s.pts_gained || 0}</span>
                    <span class="pts">${s.score ?? 0}</span>
                </div>`).join(""));
        }

        // Fixed column count by suspect total, then zoom the stage down until it fits without scrolling.
        // In reveal it measures the opened end state, so the files never outgrow the screen mid-animation.
        let fitKey = "";
        function fit() {
            const stage = $("stage"), files = $("files"), fs = fileEls(), n = fs.length, reveal = prevPhase === "reveal";
            if (files) files.style.gridTemplateColumns = `repeat(${n <= 3 ? Math.max(n, 1) : n === 4 ? 2 : n <= 9 ? 3 : 4}, minmax(0, 1fr))`;
            const had = body.classList.contains("revealed"), opened = fs.map(f => f.classList.contains("open"));
            body.classList.add("fitting");
            if (reveal) { body.classList.add("revealed"); fs.forEach(f => f.classList.add("open")); }
            let z = 1; stage.style.zoom = 1;
            while (z > 0.4 && document.documentElement.scrollHeight > innerHeight) { z -= 0.03; stage.style.zoom = z; }
            body.classList.toggle("revealed", had); fs.forEach((f, i) => f.classList.toggle("open", opened[i]));
            void body.offsetWidth; body.classList.remove("fitting");
        }
        addEventListener("resize", fit);

        const later = (ms, fn) => timers.push(setTimeout(fn, ms));
        const fileEls = () => [...document.querySelectorAll("#files .file")];

        // Accusation -> reveal: gavel strike, accused files lift, every file opens, stamps land.
        function enterReveal(animated, picked) {
            timers.forEach(clearTimeout); timers = [];
            const fs = fileEls();
            if (!animated) {
                fs.forEach(f => { f.classList.toggle("selected", picked.has(f.dataset.id)); f.classList.add("open", "stamped"); });
                body.classList.add("revealed");
                return;
            }
            const g = $("gavel");
            g.classList.remove("hit"); void g.offsetWidth; g.classList.add("hit");
            later(600, () => document.querySelector(".tv").classList.add("shake"));
            later(1100, () => document.querySelector(".tv").classList.remove("shake"));
            later(1500, () => fs.forEach(f => f.classList.toggle("selected", picked.has(f.dataset.id))));
            later(2600, () => {
                body.classList.add("revealed");
                fs.forEach((f, i) => later(i * 160, () => f.classList.add("open")));
            });
            later(3500, () => fs.forEach((f, i) => later(i * 320, () => f.classList.add("stamped"))));
        }

        function leaveReveal() {
            timers.forEach(clearTimeout); timers = [];
            body.classList.remove("revealed");
            $("gavel").classList.remove("hit");
            fileEls().forEach(f => f.classList.remove("selected", "open", "stamped"));
        }

        async function updateDisplay() {
            try {
                const res = await fetch("/api/state?role=player&_t=" + Date.now(), { cache: "no-store" });
                const state = await res.json();
                const phase = state.phase;
                const idx = PHASES.findIndex(p => p[0] === phase);
                setHTML($("case-no"), `Case file &middot; Round ${state.round}`);
                setHTML($("phases"), PHASES.map(([k, label], i) => `<li class="${i < idx ? "done" : i === idx ? "now" : ""}">${label}</li>`).join(""));

                let revealNow = null;
                if (phase !== prevPhase) {
                    if (prevPhase === "reveal") leaveReveal();
                    if (phase === "reveal") revealNow = { animated: prevPhase === "voting" };
                    body.dataset.phase = phase; phaseSince = Date.now(); prevPhase = phase;
                }
                // The accusation heartbeat quickens once the vote has dragged on for 30s.
                body.style.setProperty("--beat", phase === "voting" && Date.now() - phaseSince > 30000 ? "0.8s" : "1.1s");

                if (phase === "lobby") {
                    mode = "lobby";
                    setHTML($("stage"), lobby(state));
                    const k = "lobby|" + (state.players || []).length;
                    if (k !== fitKey) { fitKey = k; requestAnimationFrame(fit); }
                    return;
                }
                if (mode !== "case") { $("stage").innerHTML = CASE; $("stage").dataset.h = ""; mode = "case"; }
                const r = state.last_results || {};
                const picked = new Set(((r.picked_players && r.picked_players.length) ? r.picked_players : (r.picked_player ? [r.picked_player] : [])).map(p => p.id));
                brief(state);
                files(state, picked);
                if (phase === "reveal") verdict(state, picked);
                const k = [phase, state.round, fileEls().map(f => f.id).join()].join("|");
                if (k !== fitKey) { fitKey = k; fit(); }
                if (revealNow) enterReveal(revealNow.animated, picked);
            } catch (e) {
                console.error(e);
            }
        }

        // Accusation spotlight: hunts from suspect to suspect at an uneven pace.
        let lastTarget = -1;
        function hunt() {
            setTimeout(hunt, 1300 + Math.random() * 1700);
            if (body.dataset.phase !== "voting") return;
            const fs = fileEls();
            if (!fs.length) return;
            let i = Math.floor(Math.random() * fs.length);
            if (fs.length > 1 && i === lastTarget) i = (i + 1) % fs.length;
            lastTarget = i;
            fs.forEach((f, j) => f.classList.toggle("targeted", j === i));
            const rc = fs[i].getBoundingClientRect(), beam = $("beam");
            beam.style.left = (rc.left + rc.width * (0.3 + Math.random() * 0.4)) + "px";
            beam.style.top = (rc.top + rc.height * (0.3 + Math.random() * 0.4)) + "px";
        }

        setInterval(updateDisplay, 1000);
        updateDisplay();
        hunt();
    </script>
</body>
</html>
"""


def get_stage_control_html(port: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stage Controller - One of These People Is Not Lying</title>
    <link rel="stylesheet" href="/static/app.css">
    <style>
        :root {{
            --bg-dark: #0e0d0c;
            --card-bg: #171513;
            --card-hover: #2a2622;
            --border: #201d1a;
            --border-active: #e9e4d8;
            --primary: #e9e4d8;
            --primary-hover: #d8d0bd;
            --success: #5ea67e;
            --success-hover: #3f7d5b;
            --warning: #c99236;
            --danger: #e0675a;
            --text-main: #f1ece2;
            --text-muted: #a39b8c;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: var(--font-ui);
        }}
        body {{
            background: radial-gradient(circle at 50% 10%, #171513 0%, var(--bg-dark) 100%);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }}
        .controller-card {{
            background: rgba(23,21,19, 0.95);
            border: 1px solid #2a2622;
            border-radius: 24px;
            padding: 32px 28px;
            max-width: 680px;
            width: 100%;
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.7);
            text-align: center;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 16px;
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .title-group {{
            text-align: left;
        }}
        .title-group h1 {{
            font-size: 1.45rem;
            font-weight: 800;
            color: #ece7dc;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .title-group p {{
            font-size: 0.82rem;
            color: var(--text-muted);
            margin-top: 3px;
        }}
        .badge-live {{
            background: rgba(94,166,126, 0.15);
            color: var(--success);
            border: 1px solid var(--success);
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .dot-pulse {{
            width: 8px;
            height: 8px;
            background: var(--success);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--success);
        }}
        
        .active-stage-card {{
            background: rgba(233,228,216, 0.18);
            border: 2px solid var(--primary);
            border-radius: 18px;
            padding: 24px 20px;
            margin-bottom: 24px;
            box-shadow: 0 10px 30px rgba(233,228,216, 0.2);
            transition: all 0.3s ease;
        }}
        .stage-indicator-top {{
            font-size: 0.85rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: #e9e4d8;
            margin-bottom: 6px;
        }}
        .stage-title {{
            font-size: 2rem;
            font-weight: 900;
            color: #f6f1e7;
            margin-bottom: 10px;
            letter-spacing: -0.5px;
        }}
        .stage-desc {{
            font-size: 0.92rem;
            color: #d3cbbb;
            line-height: 1.5;
            max-width: 520px;
            margin: 0 auto;
        }}

        .stepper-label {{
            font-size: 0.8rem;
            font-weight: 800;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            text-align: left;
            margin-bottom: 12px;
        }}
        .stepper-grid {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 8px;
            margin-bottom: 24px;
        }}
        .step-btn {{
            background: #171513;
            border: 1px solid #2e2a25;
            color: #a39b8c;
            padding: 12px 6px;
            border-radius: 12px;
            cursor: pointer;
            font-size: 0.8rem;
            font-weight: 700;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
            transition: all 0.2s ease;
        }}
        .step-btn:hover {{
            background: #201d1a;
            border-color: #c9bfa8;
            color: #ece7dc;
            transform: translateY(-2px);
        }}
        .step-btn.active {{
            background: #e9e4d8;
            border-color: #d8d0bd;
            color: var(--paper-ink);
            box-shadow: none;
        }}
        .step-num {{
            font-size: 0.72rem;
            opacity: 0.85;
            font-weight: 800;
        }}
        .step-icon {{
            font-size: 1.25rem;
        }}

        .actions-group {{
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-bottom: 24px;
        }}
        .btn {{
            width: 100%;
            padding: 16px;
            border-radius: 14px;
            font-size: 1.05rem;
            font-weight: 800;
            cursor: pointer;
            border: none;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            transition: all 0.2s ease;
        }}
        .btn-advance {{
            background: #e9e4d8;
            color: var(--paper-ink);
            box-shadow: none;
        }}
        .btn-advance:hover {{
            background: #d8d0bd;
            transform: translateY(-2px);
            box-shadow: none;
        }}
        .btn-next-round {{
            background: #5ea67e;
            color: var(--paper-ink);
            box-shadow: none;
        }}
        .btn-next-round:hover {{
            background: #3f7d5b;
            transform: translateY(-2px);
        }}
        .btn-reset {{
            background: rgba(224,103,90, 0.12);
            color: #eda79e;
            border: 1px solid rgba(224,103,90, 0.4);
            padding: 12px;
            font-size: 0.9rem;
        }}
        .btn-reset:hover {{
            background: rgba(224,103,90, 0.25);
            border-color: #e0675a;
            color: var(--text);
        }}

        .spoiler-shield {{
            background: rgba(94,166,126, 0.08);
            border: 1px solid rgba(94,166,126, 0.3);
            border-radius: 12px;
            padding: 12px 16px;
            font-size: 0.82rem;
            color: #bfe0cb;
            display: flex;
            align-items: center;
            gap: 10px;
            text-align: left;
            margin-bottom: 20px;
        }}
        .spoiler-shield span {{
            font-size: 1.25rem;
        }}

        .role-counter-input {{
            width: 65px;
            background: #0e0d0c;
            border: 1px solid #3a352e;
            color: #f6f1e7;
            padding: 8px 10px;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 800;
            text-align: center;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }}
        .role-counter-input:focus {{
            border-color: var(--primary);
            box-shadow: 0 0 0 2px rgba(233,228,216, 0.25);
        }}

        .footer-links {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 16px;
            font-size: 0.85rem;
            color: var(--text-muted);
            flex-wrap: wrap;
            border-top: 1px solid #201d1a;
            padding-top: 16px;
        }}
        .footer-links a {{
            color: #e2d6b8;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 4px;
            transition: color 0.2s;
        }}
        .footer-links a:hover {{
            color: #e9e4d8;
            text-decoration: underline;
        }}
        .footer-links a.warning-link {{
            color: #d9a441;
            opacity: 0.85;
        }}
        .footer-links a.warning-link:hover {{
            opacity: 1;
        }}

        .toast {{
            position: fixed;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%);
            background: #201d1a;
            border: 1px solid #c9bfa8;
            color: #ece7dc;
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 700;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            display: none;
            z-index: 100;
        }}

        @media (max-width: 600px) {{
            .stepper-grid {{
                grid-template-columns: repeat(3, 1fr);
            }}
            .controller-card {{
                padding: 20px 16px;
            }}
            .stage-title {{
                font-size: 1.6rem;
            }}
        }}
    </style>
</head>
<body class="theme-noir">
    <div class="controller-card">
        <div class="header">
            <div class="title-group">
                <h1>Stage Controller</h1>
                <p>Admin host navigator &bull; Zero player info &bull; Spoiler-free</p>
            </div>
            <div class="badge-live">
                <div class="dot-pulse"></div>
                <span>Live Monitor</span>
            </div>
        </div>

        <div class="active-stage-card" id="stage-card">
            <div class="stage-indicator-top" id="round-badge">Round 1 &bull; Loading...</div>
            <div class="stage-title" id="stage-name-display">Lobby</div>
            <div class="stage-desc" id="stage-description">
                Loading game status...
            </div>
        </div>

        <!-- Role Quantities Configuration (Spoiler-Free) -->
        <div class="role-config-card" style="background: rgba(14,13,12, 0.7); border: 1px solid #201d1a; border-radius: 16px; padding: 14px 18px; margin-bottom: 20px; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 14px;">
            <div style="text-align: left;">
                <div style="font-size: 0.92rem; font-weight: 800; color: #ece7dc; display: flex; align-items: center; gap: 6px;">
                    <span>Role Quantities (Larger Parties)</span>
                </div>
                <div style="font-size: 0.75rem; color: #a39b8c; margin-top: 2px;">
                    Remaining players become Liars. Fully blind &amp; spoiler-free!
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <label for="ctrl-guesser-count" style="font-size: 0.82rem; font-weight: 700; color: #d9a441; display: flex; align-items: center; gap: 4px;">
                        <span>Guessers:</span>
                    </label>
                    <input type="number" id="ctrl-guesser-count" min="1" max="20" value="1" oninput="updateRoleCounts()" onchange="updateRoleCounts()" class="role-counter-input">
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <label for="ctrl-truth-count" style="font-size: 0.82rem; font-weight: 700; color: #7cc19a; display: flex; align-items: center; gap: 4px;">
                        <span>Truth Tellers:</span>
                    </label>
                    <input type="number" id="ctrl-truth-count" min="1" max="20" value="1" oninput="updateRoleCounts()" onchange="updateRoleCounts()" class="role-counter-input">
                </div>
            </div>
            <div id="ctrl-role-status" style="width: 100%; margin-top: 6px;"></div>
        </div>

        <div class="stepper-label">Jump to Any Game Stage:</div>
        <div class="stepper-grid">
            <button class="step-btn" id="step-btn-lobby" onclick="setPhase('lobby')">
                <span class="step-num">STAGE 1</span>
                <span class="step-icon">1</span>
                <span>Lobby</span>
            </button>
            <button class="step-btn" id="step-btn-setup" onclick="setPhase('setup')">
                <span class="step-num">STAGE 2</span>
                <span class="step-icon">2</span>
                <span>Secrets</span>
            </button>
            <button class="step-btn" id="step-btn-questioning" onclick="setPhase('questioning')">
                <span class="step-num">STAGE 3</span>
                <span class="step-icon">3</span>
                <span>Questioning</span>
            </button>
            <button class="step-btn" id="step-btn-voting" onclick="setPhase('voting')">
                <span class="step-num">STAGE 4</span>
                <span class="step-icon">4</span>
                <span>Accusation</span>
            </button>
            <button class="step-btn" id="step-btn-reveal" onclick="setPhase('reveal')">
                <span class="step-num">STAGE 5</span>
                <span class="step-icon">5</span>
                <span>Reveal</span>
            </button>
        </div>

        <div class="actions-group">
            <button class="btn btn-advance" id="ctrl-advance-btn" onclick="nextPhase()">
                <span><svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-play"/></svg> Advance to Next Stage <svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-chevron-right"/></svg></span>
            </button>
            <button class="btn btn-next-round" id="next-round-btn" onclick="nextRound()" style="display: none;">
                <span>Start New Round (Shuffle &amp; Start) <svg class="icon" aria-hidden="true"><use href="/static/icons.svg#i-chevron-right"/></svg></span>
            </button>
            <button class="btn btn-reset" id="ctrl-reset-btn" onclick="terminateToLobby()">
                <span id="ctrl-reset-btn-label">End Game &amp; Return to Lobby</span>
            </button>
        </div>

        <div class="spoiler-shield">
            
            <div>
                <strong>Blind Host Participation:</strong> This tab intentionally displays <strong>strictly NO roles, topics, or statements</strong>. You can participate on your phone without seeing any secrets!
            </div>
        </div>

        <div class="footer-links">
            <a href="/qr" target="_blank">Lobby QR Tab</a>
            <span>&bull;</span>
            <a href="/join" target="_blank">Play via Browser</a>
            <span>&bull;</span>
            <a href="/display" target="_blank">Public TV Display</a>
            <span>&bull;</span>
            <a href="/admin#logs-card" target="_blank" style="color: #c9bfa8;">Live Terminal & Logs</a>
            <span>&bull;</span>
            <a href="/admin" target="_blank" class="warning-link">Full Admin Dossier (Spoilers)</a>
        </div>
    </div>

    <div class="toast" id="toast"></div>

    <script>
        const STAGE_INFO = {{
            "lobby": {{
                name: "1. Lobby (Waiting Room)",
                desc: "Players connect via the Lobby QR tab. When everyone has entered the lobby, advance to Setup & Secrets to begin the round!"
            }},
            "setup": {{
                name: "2. Setup & Secrets Briefing",
                desc: "Secret topics & statements are delivered to player phones. Suspects review their stories. When everyone is ready, advance to Questioning!"
            }},
            "questioning": {{
                name: "3. Questioning Phase (Untimed)",
                desc: "Interrogation in progress. The Guesser questions suspects and suspects defend their statements. The Guesser can also advance on their own phone when ready!"
            }},
            "voting": {{
                name: "4. Guesser Accusation",
                desc: "The Guesser chooses which suspect they believe is telling the truth. Once the Guesser taps their accusation on their phone, the result reveals automatically!"
            }},
            "reveal": {{
                name: "5. Truth Reveal & Standings",
                desc: "Round concluded! Outcome, the real truth, and current standings are displayed across all player phones and screens. Review the score and click Next Round when ready!"
            }}
        }};

        let currentPhase = "";
        let currentRound = 1;

        function showToast(msg) {{
            const t = document.getElementById("toast");
            if (!t) return;
            t.innerText = msg;
            t.style.display = "block";
            setTimeout(() => {{ t.style.display = "none"; }}, 2500);
        }}

        async function fetchState() {{
            try {{
                const res = await fetch("/api/state?role=player&_t=" + Date.now(), {{ cache: "no-store" }});
                if (!res.ok) return;
                const state = await res.json();
                
                currentPhase = state.phase || "lobby";
                currentRound = state.round || 1;

                // Update Round Badge
                const roundBadge = document.getElementById("round-badge");
                if (roundBadge) {{
                    roundBadge.innerText = `Round ${{currentRound}} • STAGE CONTROLLER`;
                }}

                // Update Active Stage Display
                const info = STAGE_INFO[currentPhase] || {{ name: currentPhase.toUpperCase(), desc: "" }};
                const stageNameEl = document.getElementById("stage-name-display");
                const stageDescEl = document.getElementById("stage-description");
                if (stageNameEl) stageNameEl.innerText = info.name;
                if (stageDescEl) stageDescEl.innerText = info.desc;

                // Update Stepper Buttons
                ["lobby", "setup", "questioning", "voting", "reveal"].forEach(p => {{
                    const btn = document.getElementById("step-btn-" + p);
                    if (btn) {{
                        if (p === currentPhase) {{
                            btn.classList.add("active");
                        }} else {{
                            btn.classList.remove("active");
                        }}
                    }}
                }});

                // When a round reaches its end (reveal phase):
                // 1) Remove the advance button so the only two options are to start a new round or terminate to lobby
                // 2) Disable previous phase stepper buttons to prevent accidentally returning to a previous phase
                const isReveal = (currentPhase === "reveal");
                const advanceBtn = document.getElementById("ctrl-advance-btn");
                const nextRoundBtn = document.getElementById("next-round-btn");
                const resetBtn = document.getElementById("ctrl-reset-btn");
                const resetLabel = document.getElementById("ctrl-reset-btn-label");

                if (advanceBtn) {{
                    advanceBtn.style.display = isReveal ? "none" : "flex";
                }}
                if (nextRoundBtn) {{
                    nextRoundBtn.style.display = isReveal ? "flex" : "none";
                }}
                if (resetBtn) {{
                    resetBtn.style.display = "flex";
                    if (isReveal) {{
                        resetBtn.style.background = "#b3412f";
                        resetBtn.style.color = "#fff8ea";
                        resetBtn.style.boxShadow = "none";
                        resetBtn.style.border = "none";
                        if (resetLabel) resetLabel.innerHTML = "End Game &amp; Return to Lobby";
                    }} else {{
                        resetBtn.style.background = "rgba(224,103,90, 0.12)";
                        resetBtn.style.color = "#eda79e";
                        resetBtn.style.boxShadow = "none";
                        resetBtn.style.border = "1px solid rgba(224,103,90, 0.4)";
                        if (resetLabel) resetLabel.innerHTML = "End Game &amp; Return to Lobby";
                    }}
                }}

                // Prevent returning to previous phase during reveal
                ["setup", "questioning", "voting"].forEach(p => {{
                    const btn = document.getElementById("step-btn-" + p);
                    if (btn) {{
                        if (isReveal) {{
                            btn.style.opacity = "0.35";
                            btn.style.cursor = "not-allowed";
                            btn.style.pointerEvents = "none";
                        }} else {{
                            btn.style.opacity = "1";
                            btn.style.cursor = "pointer";
                            btn.style.pointerEvents = "auto";
                        }}
                    }}
                }});

                // Update Role Count inputs if not currently focused
                const gInput = document.getElementById("ctrl-guesser-count");
                const ttInput = document.getElementById("ctrl-truth-count");
                if (gInput && document.activeElement !== gInput) {{
                    gInput.value = state.target_guesser_count || 1;
                }}
                if (ttInput && document.activeElement !== ttInput) {{
                    ttInput.value = state.target_truth_teller_count || 1;
                }}

                // Update Role Requirements Status
                const req = state.role_requirements;
                const statusEl = document.getElementById("ctrl-role-status");
                if (statusEl && req) {{
                    if (req.valid) {{
                        statusEl.innerHTML = `
                            <div style="padding: 6px 12px; background: rgba(94,166,126, 0.15); border: 1px solid #5ea67e; border-radius: 6px; font-size: 0.8rem; color: #9fd2b3; font-weight: 700;">
                                Valid Setup: ${{req.guessers}} Guesser(s) &bull; ${{req.truth_tellers}} Truth Teller(s) &bull; ${{req.liars}} Liar(s) (${{req.players}} players total)
                            </div>
                        `;
                    }} else {{
                        statusEl.innerHTML = `
                            <div style="padding: 6px 12px; background: rgba(224,103,90, 0.2); border: 1px solid #e0675a; border-radius: 6px; font-size: 0.8rem; color: #eda79e; font-weight: 700;">
                                ${{escapeHtml(req.error)}}
                            </div>
                        `;
                    }}
                }}

            }} catch (e) {{
                console.error("State polling error:", e);
            }}
        }}

        async function updateRoleCounts() {{
            const gInput = document.getElementById("ctrl-guesser-count");
            const ttInput = document.getElementById("ctrl-truth-count");
            const gCount = parseInt(gInput ? gInput.value : 1) || 1;
            const ttCount = parseInt(ttInput ? ttInput.value : 1) || 1;
            try {{
                const res = await fetch("/api/action", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{
                        action: "set_role_counts",
                        guesser_count: gCount,
                        truth_teller_count: ttCount,
                        apply_now: true
                    }})
                }});
                const data = await res.json();
                if (res.ok) {{
                    showToast(`Role counts updated: ${{gCount}} Guesser(s), ${{ttCount}} Truth Teller(s)`);
                    fetchState();
                }} else {{
                    const msg = (data && data.error) ? data.error : "Failed to update role counts";
                    showToast(msg, 5000);
                    alert(msg);
                }}
            }} catch(e) {{
                showToast("Error updating role counts: " + e);
            }}
        }}

        async function setPhase(phase) {{
            try {{
                const res = await fetch("/api/action", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ action: "set_phase", phase: phase }})
                }});
                const data = await res.json();
                if (res.ok) {{
                    showToast("Switched stage to: " + phase.toUpperCase());
                    fetchState();
                }} else {{
                    const msg = (data && data.error) ? data.error : "Cannot switch stage";
                    showToast(msg, 5000);
                    alert(msg);
                }}
            }} catch(e) {{
                showToast("Error switching stage: " + e);
            }}
        }}

        async function nextPhase() {{
            try {{
                const res = await fetch("/api/action", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ action: "next_phase" }})
                }});
                const data = await res.json();
                if (res.ok) {{
                    showToast("Advanced to next stage!");
                    fetchState();
                }} else {{
                    const msg = (data && data.error) ? data.error : "Cannot advance stage";
                    showToast(msg, 5000);
                    alert(msg);
                }}
            }} catch(e) {{
                showToast("Error advancing stage: " + e);
            }}
        }}

        async function nextRound() {{
            try {{
                const res = await fetch("/api/action", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ action: "next_round" }})
                }});
                const data = await res.json();
                if (res.ok) {{
                    showToast("Started Next Round!");
                    fetchState();
                }} else {{
                    const msg = (data && data.error) ? data.error : "Cannot start next round";
                    showToast(msg, 5000);
                    alert(msg);
                }}
            }} catch(e) {{
                showToast("Error starting next round: " + e);
            }}
        }}

        async function resetGame() {{
            if (!confirm("Are you sure you want to reset the game back to Round 1 Lobby? All scores will be reset.")) return;
            try {{
                const res = await fetch("/api/action", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ action: "reset_game" }})
                }});
                if (res.ok) {{
                    showToast("Game reset to Lobby!");
                    fetchState();
                }}
            }} catch(e) {{
                showToast("Error resetting game: " + e);
            }}
        }}

        async function terminateToLobby() {{
            if (!confirm("End the game? The player with the most points gets the win on the leaderboard, scores reset and a fresh lobby starts.")) return;
            try {{
                const res = await fetch("/api/action", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{ action: "end_game" }})
                }});
                if (res.ok) {{
                    showToast("Game terminated and returned to Lobby!");
                    fetchState();
                }}
            }} catch(e) {{
                showToast("Error terminating game: " + e);
            }}
        }}

        window.logsUserScrolled = false;
        const logsEl = document.getElementById("logs-list");
        if (logsEl) {{
            logsEl.addEventListener("scroll", () => {{
                const atBottom = logsEl.scrollHeight - logsEl.scrollTop <= logsEl.clientHeight + 30;
                window.logsUserScrolled = !atBottom;
            }});
        }}

        setInterval(fetchState, 1000);
        fetchState();
    </script>
</body>
</html>
"""


def get_admin_login_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login - One of These People Is Not Lying</title>
    <link rel="stylesheet" href="/static/app.css">
</head>
<body class="theme-noir page-center">
    <main class="login-card">
        <div class="eyebrow">Restricted</div>
        <h1 class="display-title">Admin Console</h1>
        <form method="post" action="/api/admin/login">
            <input type="hidden" name="next" id="next" value="/admin">
            <label class="field-label" for="username">Username</label>
            <input id="username" name="username" autocomplete="username" required autofocus>
            <label class="field-label" for="password">Password</label>
            <input id="password" name="password" type="password" autocomplete="current-password" required>
            <div class="form-error" id="err" role="alert"></div>
            <button class="btn btn-primary btn-block" type="submit">Sign in</button>
        </form>
        <a class="muted-link" href="/join">Joining as a player? Go to /join</a>
    </main>
    <script>
        const q = new URLSearchParams(location.search);
        if (q.get("next")) document.getElementById("next").value = q.get("next");
        if (q.get("error")) document.getElementById("err").innerText = "Wrong username or password.";
    </script>
</body>
</html>
"""
