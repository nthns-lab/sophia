#!/usr/bin/env bash
# SOPHIA 설치 — Claude Code 네이티브 인스톨러와 같은 레이아웃·UX.
#   ~/.local/share/sophia/   ← 패키지 본체 (버전 보관소)
#   ~/.local/bin/sophia      ← 실행 런처 (경로가 설치 시점에 박힘 = 환경변수 불필요)
#
# 두 가지 방식 모두 지원:
#   1) curl 한 줄 (claude 처럼):
#        curl -fsSL https://nthns-lab.github.io/sophia/install.sh | bash
#      → 소스가 옆에 없으므로 스스로 git clone(또는 tarball) 으로 받아온다.
#   2) 레포 안에서:
#        ./install.sh
#      → 옆의 sophia/ 를 바로 복사.
#
# 제거:  curl ... | bash -s -- --uninstall   또는   ./install.sh --uninstall
#
# 요구: python3 (3.11+). pip 불필요 — 순수 표준 라이브러리.
# 선택: claude/codex CLI 가 PATH 에 있으면 `sophia --real` 로 실제 위임.
set -euo pipefail

REPO="${SOPHIA_REPO:-nthns-lab/sophia}"
BRANCH="${SOPHIA_BRANCH:-main}"
SHARE_DIR="$HOME/.local/share/sophia"
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/sophia"

uninstall() {
  rm -f "$LAUNCHER"
  rm -rf "$SHARE_DIR"
  echo "✓ sophia 제거 완료 ($LAUNCHER, $SHARE_DIR)"
  exit 0
}
[ "${1:-}" = "--uninstall" ] && uninstall

# 1) python3 확인
if ! command -v python3 >/dev/null 2>&1; then
  echo "✗ python3 가 필요합니다 (3.11+). 설치 후 다시 실행하세요." >&2
  exit 1
fi
PYVER=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
echo "• python3 $PYVER 발견"

# 2) 소스 위치 결정 — 로컬(레포 안)인지, curl 파이프인지.
#    BASH_SOURCE 가 실제 파일이고 옆에 sophia/ 가 있으면 로컬.
LOCAL_DIR=""
if [ -n "${BASH_SOURCE:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  cand="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  [ -d "$cand/sophia" ] && LOCAL_DIR="$cand"
fi

TMP_DIR=""
cleanup() { [ -n "$TMP_DIR" ] && rm -rf "$TMP_DIR"; }
trap cleanup EXIT

if [ -n "$LOCAL_DIR" ]; then
  SRC_DIR="$LOCAL_DIR"
  echo "• 로컬 소스 사용: $SRC_DIR"
else
  # curl | bash 경로 — 소스를 받아온다 (git 우선, 없으면 tarball)
  TMP_DIR="$(mktemp -d)"
  if command -v git >/dev/null 2>&1; then
    echo "• 소스 받는 중 (git clone $REPO@$BRANCH)…"
    git clone --depth 1 --branch "$BRANCH" "https://github.com/$REPO.git" "$TMP_DIR/src" >/dev/null 2>&1
    SRC_DIR="$TMP_DIR/src"
  elif command -v curl >/dev/null 2>&1; then
    echo "• 소스 받는 중 (tarball)…"
    curl -fsSL "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" \
      | tar -xz -C "$TMP_DIR"
    SRC_DIR="$TMP_DIR/sophia-$BRANCH"
  else
    echo "✗ git 또는 curl 이 필요합니다 (소스 다운로드용)." >&2
    exit 1
  fi
  if [ ! -d "$SRC_DIR/sophia" ]; then
    echo "✗ 소스를 받지 못했습니다 ($REPO@$BRANCH 확인)." >&2
    exit 1
  fi
fi

# 3) 패키지 본체 설치 (~/.local/share/sophia)
echo "• 패키지 설치 → $SHARE_DIR"
rm -rf "$SHARE_DIR"
mkdir -p "$SHARE_DIR"
cp -R "$SRC_DIR/sophia" "$SHARE_DIR/sophia"
cp -f "$SRC_DIR/README.md" "$SHARE_DIR/" 2>/dev/null || true

# 4) 런처 생성 (경로를 여기서 박는다 → 환경변수 0개)
echo "• 런처 설치 → $LAUNCHER"
mkdir -p "$BIN_DIR"
cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
# SOPHIA 런처 (install.sh 가 생성). 경로가 박혀 있어 추가 설정 불필요.
exec python3 -c "import sys; sys.path.insert(0, '$SHARE_DIR'); from sophia.__main__ import main; main()" "\$@"
EOF
chmod +x "$LAUNCHER"

# 5) 안내 (claude 도 ~/.local/bin 을 쓴다)
echo ""
echo "✓ 설치 완료. 이제 'sophia' 로 실행하세요."
echo "    sophia --goal \"무언가를 만든다\"     # 오프라인 데모 (키 불필요)"
echo "    sophia tui                          # 포트폴리오 대시보드"
echo "    sophia --real --goal \"...\"          # 실제 claude 일꾼에 위임"
if ! echo ":$PATH:" | grep -q ":$BIN_DIR:"; then
  # 셸 감지 — 맥(zsh 기본)은 ~/.zshrc, bash 는 ~/.bashrc. SHELL 환경변수로 판별.
  case "${SHELL:-}" in
    */zsh) RC="$HOME/.zshrc" ;;
    */bash) RC="$HOME/.bashrc" ;;
    *) RC="셸 설정 파일" ;;
  esac
  echo ""
  echo "⚠  $BIN_DIR 가 PATH 에 없습니다. 아래를 $RC 에 추가한 뒤 새 터미널을 여세요:"
  echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
  echo "  (바로 적용하려면 같은 줄을 현재 셸에 붙여넣으세요.)"
fi
