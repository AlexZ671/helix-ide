"""Map Helix language names / file extensions to a display label and an icon.

Icons are served straight from public URLs (raster PNGs); arRPC/Vesktop fetches
external image URLs, so no Discord app or uploaded art assets are required.
Language icons: github.com/marwin1991/profile-technology-icons (PNG set).
"""

import os

_ICONS = "https://raw.githubusercontent.com/marwin1991/profile-technology-icons/main/icons"
HELIX_LOGO = "https://raw.githubusercontent.com/helix-editor/helix/master/contrib/helix.png"

# Helix file-type name -> (pretty label, icon filename in the _ICONS repo or None)
BY_LANG = {
    "rust": ("Rust", "rust.png"),
    "python": ("Python", "python.png"),
    "c-sharp": ("C#", "c%23.png"),
    "javascript": ("JavaScript", "javascript.png"),
    "jsx": ("JavaScript (JSX)", "javascript.png"),
    "typescript": ("TypeScript", "typescript.png"),
    "tsx": ("TypeScript (TSX)", "typescript.png"),
    "c": ("C", "c.png"),
    "cpp": ("C++", "c%2B%2B.png"),
    "go": ("Go", "go.png"),
    "java": ("Java", "java.png"),
    "kotlin": ("Kotlin", "kotlin.png"),
    "ruby": ("Ruby", "ruby.png"),
    "php": ("PHP", "php.png"),
    "html": ("HTML", "html.png"),
    "css": ("CSS", "css.png"),
    "scss": ("SCSS", "sass.png"),
    "bash": ("Shell", "bash.png"),
    "sh": ("Shell", "bash.png"),
    "lua": ("Lua", "lua.png"),
    "sql": ("SQL", "sqlite.png"),
    "dockerfile": ("Dockerfile", "docker.png"),
    "zig": ("Zig", "ziglang.png"),
    "nix": ("Nix", "nixos.png"),
    "dart": ("Dart", "dart.png"),
    "elixir": ("Elixir", "elixir.png"),
    "scala": ("Scala", "scala.png"),
    "swift": ("Swift", "swift.png"),
    "go-mod": ("Go", "go.png"),
    # No dedicated icon -> fall back to the Helix logo, text still names them:
    "json": ("JSON", None),
    "toml": ("TOML", None),
    "yaml": ("YAML", None),
    "markdown": ("Markdown", None),
    "haskell": ("Haskell", None),
    "scheme": ("Scheme", None),
    "git-commit": ("Git commit", "git.png"),
    "make": ("Makefile", None),
}

# Fallback: file extension -> Helix language name (when statusline omits file-type)
BY_EXT = {
    ".rs": "rust", ".py": "python", ".cs": "c-sharp", ".csx": "c-sharp",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".jsx": "jsx", ".ts": "typescript", ".tsx": "tsx", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp",
    ".go": "go", ".java": "java", ".kt": "kotlin", ".rb": "ruby",
    ".php": "php", ".html": "html", ".htm": "html", ".css": "css",
    ".scss": "scss", ".json": "json", ".toml": "toml", ".yaml": "yaml",
    ".yml": "yaml", ".md": "markdown", ".sh": "bash", ".bash": "bash",
    ".lua": "lua", ".hs": "haskell", ".scm": "scheme", ".sql": "sql",
    ".zig": "zig", ".nix": "nix", ".dart": "dart", ".ex": "elixir",
    ".exs": "elixir", ".scala": "scala", ".swift": "swift",
}

DEFAULT = ("Text", None)


def _icon_url(filename):
    return f"{_ICONS}/{filename}" if filename else HELIX_LOGO


def resolve(filename: str | None, file_type: str | None):
    """Return (pretty_label, icon_url) for the given filename and/or the
    file-type Helix reported in its statusline. icon_url always points at a
    real PNG (the Helix logo when the language has no dedicated icon)."""
    if file_type and file_type in BY_LANG:
        label, icon = BY_LANG[file_type]
        return label, _icon_url(icon)
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        lang = BY_EXT.get(ext)
        if lang and lang in BY_LANG:
            label, icon = BY_LANG[lang]
            return label, _icon_url(icon)
    if file_type:  # unknown but Helix told us something
        return file_type.replace("-", " ").title(), HELIX_LOGO
    return DEFAULT[0], HELIX_LOGO
