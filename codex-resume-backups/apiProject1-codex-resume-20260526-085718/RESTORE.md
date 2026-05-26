# Codex Resume History Backup

Project: /home/alextub/Documents/apiProject1
Created: 20260526-085718

Contents:
- .codex/sessions/: project-specific Codex resume session JSONL files, preserving Codex directory layout.
- .codex/history.project.jsonl: prompt history rows whose session_id belongs to this project backup.
- .codex/session_index.project.jsonl: matching session-index rows if present.
- meta/session-ids.txt and meta/session-files-*.txt: audit lists used to build this backup.

Restore on another PC:
1. Install/login to Codex on the new PC once so ~/.codex exists.
2. Extract this archive.
3. Copy the extracted .codex/sessions/ contents into ~/.codex/sessions/.
4. Optionally append .codex/history.project.jsonl to ~/.codex/history.jsonl and .codex/session_index.project.jsonl to ~/.codex/session_index.jsonl.

Note: the session files contain the original cwd /home/alextub/Documents/apiProject1. For easiest resume behavior, keep the project at the same path on the new PC, or replace that path in the copied session JSONL files before resuming.
