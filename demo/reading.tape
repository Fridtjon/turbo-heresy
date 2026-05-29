# turbo-heresy — the reading-view still for the website (website/reading.png).
#
#   vhs demo/reading.tape   (needs ./target/release/turbo-heresy)
#
# Opens Paradise Lost, Book I (Liber I) at its famous opening lines, in the
# Abyssal palette. Sized to match the <img class="shot"> 1200x720 slot.

Output demo/_reading-trace.gif

Set Shell        "bash"
Set Width        1200
Set Height       720
Set Padding      20
Set Theme        "Catppuccin Mocha"
Set FontSize     16
Set TypingSpeed  20ms

Hide
Type "export XDG_CONFIG_HOME=$(mktemp -d)"
Enter
Type "clear"
Enter
Type "./target/release/turbo-heresy --translation en-plost --book GEN --chapter 1"
Enter
Show
Sleep 2500ms

# VHS Screenshot is async — Sleep after so the quit keystroke can't leak in.
Screenshot "website/reading.png"
Sleep 500ms

Hide
Type "q"
Sleep 300ms
