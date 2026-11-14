#!/usr/bin/env python3
"""Builds the animated SVGs of the documentation, in English and Brazilian Portuguese.

One source, two languages: the drawings are defined once below and the texts
come from ``TEXTS``. Output: ``docs/img/<language>/<name>.svg``.

    python tools/build_images.py          # write the files
    python tools/build_images.py --check  # fail if the files are out of date (CI)

The SVGs use CSS animation and ``prefers-color-scheme``, both honoured when
GitHub shows an SVG through ``<img>``. No scripts. Standard library only.
"""

from __future__ import annotations

import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "img"

TEXTS = {
    "en": {
        "pipeline_title": "From git push to live, on your own server",
        "terminal_title": "A real deploy log, as GitHub Actions shows it",
        "pipeline_nodes": [
            ("git push", "deploy branch"),
            ("GitHub Actions", "opens SSH, no logic"),
            ("SSH key", "locked to 1 command"),
            ("sudo deproi", "root, on the server"),
            ("build + hooks", "image, migrations"),
            ("recreate", "docker compose up"),
            ("healthy?", "live ✓"),
        ],
        "pipeline_caption": "Each push to the branch runs this path. If the new version is not healthy, it rolls back by itself.",
        "rollback_title": "A broken version never stays live",
        "rollback_live": "live",
        "rollback_new": "new commit",
        "rollback_starting": "health: starting…",
        "rollback_unhealthy": "health: unhealthy ✗",
        "rollback_back": "rollback",
        "rollback_restored": "previous version back · healthy ✓",
        "rollback_result": "result: FAILED_ROLLED_BACK",
        "rollback_caption": "The previous image and its compose definition come back. You fix the code and push again.",
        "layers_title": "A leaked key can only trigger a deploy",
        "layers": [
            ("GitHub environment", "secrets only for the deploy branch"),
            ("authorized_keys", 'restrict, command="sudo -n deproi-<name>"'),
            ("sudo rule", 'one command, no arguments ("")'),
            ("deproi-<name>", "root-owned, outside the checkout"),
            ("/etc/deproi/<name>.json", "root decides branch, project, paths"),
        ],
        "attempts": ["other branch", "open a shell", "pass arguments", "edit the script", "change the target"],
        "blocked": "blocked",
        "layers_caption": "Each layer holds on its own. Together, the deploy key is good for exactly one thing.",
    },
    "pt-BR": {
        "pipeline_title": "Do git push ao ar, no seu próprio servidor",
        "terminal_title": "Um log real de deploy, como o GitHub Actions mostra",
        "pipeline_nodes": [
            ("git push", "branch de deploy"),
            ("GitHub Actions", "abre o SSH, sem lógica"),
            ("chave SSH", "presa a 1 comando"),
            ("sudo deproi", "root, no servidor"),
            ("build + ganchos", "imagem, migrations"),
            ("recriar", "docker compose up"),
            ("saudável?", "no ar ✓"),
        ],
        "pipeline_caption": "Cada push na branch percorre este caminho. Se a versão nova não fica saudável, ela é revertida sozinha.",
        "rollback_title": "Uma versão quebrada nunca fica no ar",
        "rollback_live": "no ar",
        "rollback_new": "commit novo",
        "rollback_starting": "saúde: iniciando…",
        "rollback_unhealthy": "saúde: unhealthy ✗",
        "rollback_back": "reversão",
        "rollback_restored": "versão anterior de volta · saudável ✓",
        "rollback_result": "result: FAILED_ROLLED_BACK",
        "rollback_caption": "Voltam a imagem anterior e a definição do compose dela. Você corrige o código e faz push de novo.",
        "layers_title": "Uma chave vazada só consegue disparar um deploy",
        "layers": [
            ("GitHub environment", "segredos só para a branch de deploy"),
            ("authorized_keys", 'restrict, command="sudo -n deproi-<nome>"'),
            ("regra do sudo", 'um comando, sem argumentos ("")'),
            ("deproi-<nome>", "dono root, fora do checkout"),
            ("/etc/deproi/<nome>.json", "root decide branch, projeto, caminhos"),
        ],
        "attempts": ["outra branch", "abrir um shell", "passar argumentos", "editar o script", "mudar o alvo"],
        "blocked": "barrado",
        "layers_caption": "Cada camada se sustenta sozinha. Juntas, a chave de deploy serve para exatamente uma coisa.",
    },
}

STYLE = """
  :root, svg {
    --bg: #ffffff; --ink: #1f2328; --muted: #59636e; --node: #f6f8fa; --edge: #d1d9e0;
    --accent: #0969da; --accent-soft: #ddf4ff; --ok: #1a7f37; --ok-soft: #dafbe1;
    --bad: #cf222e; --bad-soft: #ffebe9;
  }
  @media (prefers-color-scheme: dark) {
    :root, svg {
      --bg: #0d1117; --ink: #e6edf3; --muted: #9198a1; --node: #151b23; --edge: #3d444d;
      --accent: #4493f8; --accent-soft: #0c2d6b; --ok: #3fb950; --ok-soft: #0f3a1e;
      --bad: #f85149; --bad-soft: #4c1414;
    }
  }
  text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif; fill: var(--ink); }
  .bg { fill: var(--bg); }
  .title { font-size: 20px; font-weight: 600; }
  .caption { font-size: 13px; fill: var(--muted); }
  .label { font-size: 14px; font-weight: 600; }
  .sub { font-size: 11.5px; fill: var(--muted); }
  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
  .edge { stroke: var(--edge); stroke-width: 2; fill: none; }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; } }
"""

CYCLE = 10  # seconds


def svg(width: int, height: int, title: str, body: str, extra_style: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
        f'height="{height}" role="img" aria-label="{escape(title)}">\n'
        f"<title>{escape(title)}</title>\n<style>{STYLE}{extra_style}</style>\n"
        f'<rect class="bg" width="{width}" height="{height}" rx="16"/>\n{body}</svg>\n'
    )


def pct(seconds: float) -> str:
    return f"{seconds / CYCLE * 100:.2f}%"


def pipeline(t: dict) -> str:
    nodes = t["pipeline_nodes"]
    width, height = 1040, 270
    box_w, box_h, gap, top = 128, 76, 16, 92
    left = (width - (len(nodes) * box_w + (len(nodes) - 1) * gap)) / 2
    css, body = [], []
    body.append(f'<text class="title" x="{width / 2}" y="44" text-anchor="middle">{escape(t["pipeline_title"])}</text>')
    xs = [left + i * (box_w + gap) for i in range(len(nodes))]
    for i in range(len(nodes) - 1):
        x1, x2, y = xs[i] + box_w, xs[i + 1], top + box_h / 2
        body.append(f'<line class="edge" x1="{x1}" y1="{y}" x2="{x2}" y2="{y}"/>')
        body.append(f'<path d="M{x2 - 7},{y - 5} L{x2},{y} L{x2 - 7},{y + 5}" class="edge"/>')
    step = 1.05
    for i, (label, sub) in enumerate(nodes):
        on = 0.4 + i * step
        last = i == len(nodes) - 1
        fill, stroke = ("var(--ok-soft)", "var(--ok)") if last else ("var(--accent-soft)", "var(--accent)")
        css.append(
            f"@keyframes n{i} {{ 0%, {pct(on)} {{ fill: var(--node); stroke: var(--edge); }} "
            f"{pct(on + 0.25)}, 88% {{ fill: {fill}; stroke: {stroke}; }} 96%, 100% {{ fill: var(--node); stroke: var(--edge); }} }}\n"
            f".n{i} {{ animation: n{i} {CYCLE}s ease-in-out infinite; }}\n"
        )
        x = xs[i]
        body.append(f'<rect class="n{i}" x="{x}" y="{top}" width="{box_w}" height="{box_h}" rx="12" stroke-width="2"/>')
        body.append(
            f'<circle cx="{x + 18}" cy="{top + 18}" r="10" fill="var(--edge)"/>'
            f'<text x="{x + 18}" y="{top + 22}" text-anchor="middle" font-size="11" font-weight="700">{i + 1}</text>'
        )
        body.append(
            f'<text class="label" x="{x + box_w / 2}" y="{top + 46}" text-anchor="middle">{escape(label)}</text>'
        )
        body.append(f'<text class="sub" x="{x + box_w / 2}" y="{top + 64}" text-anchor="middle">{escape(sub)}</text>')
    # The packet travelling along the path.
    stops = []
    for i in range(len(nodes)):
        stops.append(
            f"{pct(0.4 + i * step)} {{ transform: translateX({xs[i] + box_w / 2 - xs[0] - box_w / 2:.1f}px); opacity: 1; }}"
        )
    css.append(
        "@keyframes packet { 0% { transform: translateX(0); opacity: 0; } "
        + " ".join(stops)
        + " 88% { opacity: 1; } 92%, 100% { opacity: 0; transform: translateX("
        + f"{xs[-1] - xs[0]:.1f}px); }} }}\n"
        f".packet {{ animation: packet {CYCLE}s ease-in-out infinite; }}\n"
    )
    body.append(f'<circle class="packet" cx="{xs[0] + box_w / 2}" cy="{top + box_h + 22}" r="6" fill="var(--accent)"/>')
    body.append(
        f'<line class="edge" x1="{xs[0] + box_w / 2}" y1="{top + box_h + 22}" x2="{xs[-1] + box_w / 2}" '
        f'y2="{top + box_h + 22}" stroke-dasharray="3 6"/>'
    )
    body.append(
        f'<text class="caption" x="{width / 2}" y="{height - 28}" text-anchor="middle">{escape(t["pipeline_caption"])}</text>'
    )
    return svg(width, height, t["pipeline_title"], "\n".join(body) + "\n", "".join(css))


def rollback(t: dict) -> str:
    width, height = 860, 380
    css = f"""
  @keyframes appear {{ 0%, {pct(1.0)} {{ opacity: 0; transform: translateY(8px); }} {pct(1.6)}, 90% {{ opacity: 1; transform: none; }} 97%, 100% {{ opacity: 0; }} }}
  .new {{ animation: appear {CYCLE}s ease-out infinite; }}
  @keyframes starting {{ 0%, {pct(1.6)} {{ opacity: 0; }} {pct(1.9)}, {pct(3.4)} {{ opacity: 1; }} {pct(3.6)}, 100% {{ opacity: 0; }} }}
  .starting {{ animation: starting {CYCLE}s infinite; }}
  @keyframes unhealthy {{ 0%, {pct(3.5)} {{ opacity: 0; }} {pct(3.8)}, 90% {{ opacity: 1; }} 97%, 100% {{ opacity: 0; }} }}
  .unhealthy {{ animation: unhealthy {CYCLE}s infinite; }}
  @keyframes newbox {{ 0%, {pct(3.5)} {{ stroke: var(--accent); fill: var(--accent-soft); }} {pct(3.8)}, 90% {{ stroke: var(--bad); fill: var(--bad-soft); }} 100% {{ stroke: var(--accent); fill: var(--accent-soft); }} }}
  .newbox {{ animation: newbox {CYCLE}s infinite; }}
  @keyframes draw {{ 0%, {pct(4.4)} {{ stroke-dashoffset: 520; opacity: 1; }} {pct(5.6)}, 90% {{ stroke-dashoffset: 0; opacity: 1; }} 97%, 100% {{ opacity: 0; }} }}
  .back {{ stroke-dasharray: 520; animation: draw {CYCLE}s ease-in-out infinite; }}
  @keyframes backlabel {{ 0%, {pct(5.0)} {{ opacity: 0; }} {pct(5.4)}, 90% {{ opacity: 1; }} 97%, 100% {{ opacity: 0; }} }}
  .backlabel {{ animation: backlabel {CYCLE}s infinite; }}
  @keyframes oldbox {{ 0%, {pct(1.0)} {{ fill: var(--ok-soft); stroke: var(--ok); }} {pct(1.6)}, {pct(5.6)} {{ fill: var(--node); stroke: var(--edge); }} {pct(6.2)}, 100% {{ fill: var(--ok-soft); stroke: var(--ok); }} }}
  .oldbox {{ animation: oldbox {CYCLE}s infinite; }}
  @keyframes restored {{ 0%, {pct(6.0)} {{ opacity: 0; }} {pct(6.5)}, 90% {{ opacity: 1; }} 97%, 100% {{ opacity: 0; }} }}
  .restored {{ animation: restored {CYCLE}s infinite; }}
"""
    old_x, new_x, y, w, h = 110, 530, 96, 220, 92
    body = f"""
<text class="title" x="{width / 2}" y="44" text-anchor="middle">{escape(t["rollback_title"])}</text>
<rect class="oldbox" x="{old_x}" y="{y}" width="{w}" height="{h}" rx="14" stroke-width="2"/>
<text class="label mono" x="{old_x + w / 2}" y="{y + 40}" text-anchor="middle">111111111111</text>
<text class="sub" x="{old_x + w / 2}" y="{y + 62}" text-anchor="middle">{escape(t["rollback_live"])}</text>
<line class="edge" x1="{old_x + w}" y1="{y + h / 2}" x2="{new_x}" y2="{y + h / 2}"/>
<path class="edge" d="M{new_x - 8},{y + h / 2 - 6} L{new_x},{y + h / 2} L{new_x - 8},{y + h / 2 + 6}"/>
<g class="new">
  <rect class="newbox" x="{new_x}" y="{y}" width="{w}" height="{h}" rx="14" stroke-width="2"/>
  <text class="label mono" x="{new_x + w / 2}" y="{y + 40}" text-anchor="middle">abc123def456</text>
  <text class="sub" x="{new_x + w / 2}" y="{y + 62}" text-anchor="middle">{escape(t["rollback_new"])}</text>
  <text class="sub starting" x="{new_x + w / 2}" y="{y + h + 26}" text-anchor="middle">{escape(t["rollback_starting"])}</text>
  <text class="label unhealthy" x="{new_x + w / 2}" y="{y + h + 26}" text-anchor="middle" style="fill: var(--bad)">{escape(t["rollback_unhealthy"])}</text>
</g>
<path class="edge back" d="M{new_x + w / 2},{y + h + 40} C{new_x + w / 2},{y + h + 110} {old_x + w / 2},{y + h + 110} {old_x + w / 2},{y + h + 8}" style="stroke: var(--bad); stroke-width: 2.5"/>
<text class="label backlabel" x="{width / 2}" y="{y + h + 64}" text-anchor="middle" style="fill: var(--bad)">↩ {escape(t["rollback_back"])}</text>
<g class="restored">
  <text class="label" x="{old_x + w / 2}" y="{y - 14}" text-anchor="middle" style="fill: var(--ok)">{escape(t["rollback_restored"])}</text>
  <text class="sub mono" x="{width / 2}" y="{height - 58}" text-anchor="middle">{escape(t["rollback_result"])}</text>
</g>
<text class="caption" x="{width / 2}" y="{height - 22}" text-anchor="middle">{escape(t["rollback_caption"])}</text>
"""
    return svg(width, height, t["rollback_title"], body, css)


def layers(t: dict) -> str:
    items = t["layers"]
    width, row_h, top = 900, 52, 80
    height = top + len(items) * row_h + 70
    css, body = [], []
    body.append(f'<text class="title" x="{width / 2}" y="44" text-anchor="middle">{escape(t["layers_title"])}</text>')
    for i, (label, sub) in enumerate(items):
        on = 0.6 + i * 1.4
        y = top + i * row_h
        css.append(
            f"@keyframes l{i} {{ 0%, {pct(on)} {{ fill: var(--node); stroke: var(--edge); }} "
            f"{pct(on + 0.3)}, 90% {{ fill: var(--accent-soft); stroke: var(--accent); }} 97%, 100% {{ fill: var(--node); stroke: var(--edge); }} }}\n"
            f".l{i} {{ animation: l{i} {CYCLE}s infinite; }}\n"
            f"@keyframes a{i} {{ 0%, {pct(on + 0.2)} {{ opacity: 0; transform: translateX(40px); }} "
            f"{pct(on + 0.6)}, 90% {{ opacity: 1; transform: none; }} 97%, 100% {{ opacity: 0; }} }}\n"
            f".a{i} {{ animation: a{i} {CYCLE}s ease-out infinite; }}\n"
        )
        indent = i * 14
        body.append(
            f'<rect class="l{i}" x="{30 + indent}" y="{y}" width="{560 - indent}" height="{row_h - 10}" rx="10" stroke-width="2"/>'
        )
        body.append(f'<text class="label" x="{48 + indent}" y="{y + 18}">🔒 {escape(label)}</text>')
        body.append(f'<text class="sub mono" x="{48 + indent}" y="{y + 34}">{escape(sub)}</text>')
        body.append(
            f'<g class="a{i}"><rect x="630" y="{y + 4}" width="240" height="{row_h - 18}" rx="8" fill="var(--bad-soft)" stroke="var(--bad)"/>'
            f'<text class="label" x="646" y="{y + 26}" style="fill: var(--bad)">✗ {escape(t["attempts"][i])}</text>'
            f'<text class="sub" x="856" y="{y + 26}" text-anchor="end">{escape(t["blocked"])}</text></g>'
        )
    body.append(
        f'<text class="caption" x="{width / 2}" y="{height - 26}" text-anchor="middle">{escape(t["layers_caption"])}</text>'
    )
    return svg(width, height, t["layers_title"], "\n".join(body) + "\n", "".join(css))


TERMINAL_PROMPT = {
    "en": "Actions › Deploy production › ssh deproi@server",
    "pt-BR": "Actions › Deploy production › ssh deproi@server",
}
_NOISE = (
    "#",
    " ",
    "time=",
    "DEPRECATED",
    "From ",
    "Updating ",
    "Fast-forward",
    "Total reclaimed",
    "Install ",
    "https://",
)


def terminal_lines(log: str) -> list:
    """(kind, text) lines of a real deploy log, without the build noise. Group titles get their duration."""
    lines = []
    for raw in log.splitlines():
        if not raw.strip() or raw.startswith(_NOISE) or raw == "::endgroup::":
            continue
        if raw.startswith("::group::"):
            lines.append(["group", raw[len("::group::") :]])
        elif raw.startswith("(") and raw.endswith(" s)") and lines and lines[-1][0] in ("group", "line"):
            title = next(item for item in reversed(lines) if item[0] == "group")
            title[1] += f"  ·  {raw.rsplit(': ', 1)[1][:-1]}"
        elif raw.startswith("result: "):
            lines.append(["result", raw])
        elif raw.startswith("message: "):
            lines.append(["message", raw])
        elif raw.split(":", 1)[0] in ("betterstack", "cloudflare", "webhook", "post_deploy"):
            lines.append(["extra", raw])
        elif raw.startswith("Deproi "):
            lines.append(["banner", raw])
        else:
            lines.append(["line", raw])
    return [(kind, text if len(text) <= 150 else text[:147] + "…") for kind, text in lines]


def terminal(t: dict, language: str) -> str:
    log = (ROOT / "docs" / "img" / "source" / language / "deploy.log").read_text()
    lines = [("prompt", TERMINAL_PROMPT[language]), *terminal_lines(log)]
    line_h, top, left = 19, 54, 22
    width, height = 1200, top + len(lines) * line_h + 24
    colors = {
        "prompt": "#7ee787",
        "banner": "#e6edf3",
        "group": "#79c0ff",
        "line": "#c9d1d9",
        "extra": "#8b949e",
        "message": "#e6edf3",
        "result": "#3fb950" if "SUCCESS" in log.splitlines()[-1] else "#f85149",
    }
    start, step = 0.6, 0.32
    css = []
    body = [
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="14" fill="#0d1117" stroke="#30363d"/>',
        '<circle cx="24" cy="22" r="6" fill="#ff5f57"/><circle cx="44" cy="22" r="6" fill="#febc2e"/>'
        '<circle cx="64" cy="22" r="6" fill="#28c840"/>',
        f'<line x1="0" y1="40" x2="{width}" y2="40" stroke="#30363d"/>',
    ]
    total = start + len(lines) * step
    cycle = total + 5
    for i, (kind, text) in enumerate(lines):
        at = start + i * step
        css.append(
            f"@keyframes t{i} {{ 0%, {at / cycle * 100:.2f}% {{ opacity: 0; }} {(at + 0.15) / cycle * 100:.2f}%, 95% {{ opacity: 1; }} 99%, 100% {{ opacity: 0; }} }}\n"
            f".t{i} {{ animation: t{i} {cycle:.2f}s steps(1, end) infinite; }}\n"
        )
        weight = ' font-weight="700"' if kind in ("group", "message", "result", "banner", "prompt") else ""
        prefix = "$ " if kind == "prompt" else ("▸ " if kind == "group" else "  " if kind in ("line",) else "")
        body.append(
            f'<text class="t{i} mono" x="{left}" y="{top + i * line_h + 13}" font-size="13" style="fill: {colors[kind]}"{weight}'
            f' xml:space="preserve">{escape(prefix + text)}</text>'
        )
    style = "".join(css)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="{escape(t["terminal_title"])}">\n<title>{escape(t["terminal_title"])}</title>\n'
        f"<style>{STYLE}{style}</style>\n" + "\n".join(body) + "\n</svg>\n"
    )


DRAWINGS = {"pipeline": pipeline, "rollback": rollback, "layers": layers}


def build() -> dict:
    files = {
        OUT / lang / f"{name}.svg": draw(texts) for lang, texts in TEXTS.items() for name, draw in DRAWINGS.items()
    }
    for language, texts in TEXTS.items():
        files[OUT / language / "terminal.svg"] = terminal(texts, language)
    return files


def main(argv: list) -> int:
    files = build()
    if "--check" in argv:
        stale = [str(p.relative_to(ROOT)) for p, content in files.items() if not p.exists() or p.read_text() != content]
        if stale:
            print("Out of date (run python tools/build_images.py):", ", ".join(stale))
            return 1
        print("Images: OK")
        return 0
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
