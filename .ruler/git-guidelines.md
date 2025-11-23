# Git Commit Guidelines

## Commit Message Format
- Use clear, concise commit messages that describe the actual changes
- Follow conventional commit format when appropriate (feat:, fix:, chore:, refactor:, docs:)
- Focus on the "what" and "why" of changes

## Important Commit Restrictions
- **NEVER** add Claude as co-author in commit messages
- **NEVER** add AI models as co-authors (e.g., "Co-Authored-By: GPT-5", "Co-Authored-By: Gemini-2.5-Pro", "Co-Authored-By: Claude")
- **NEVER** include "Co-Authored-By: Claude <noreply@anthropic.com>" or similar Claude Code attribution
- **NEVER** include "Generated with Claude Code" or similar AI attribution
- **NEVER** add "🤖 Generated with [Claude Code](https://claude.com/claude-code)" footer
- **NEVER** add any references to AI assistance in commit messages, including footers or Co-Authored-By AI references
- Keep commits clean and professional without AI tool references
- Commit messages should reflect the developer's work, not the tools used
- **DO NOT** use heredoc commit message format with AI attribution footers
- Expert consultations (GPT-5, Gemini, etc.) should be documented in plan/spec files, NOT in git commits

## Git Best Practices
- **Descriptive messages**: Explain what and why, not just what files changed
- **Review before commit**: Always check `git diff --cached` or `git diff` before committing
- **Atomic commits**: Each commit should represent one logical change
- **Branch strategy**: Work on feature branches when appropriate, protect main/master branch
- **Commit early, commit often**: Small, focused commits are better than large, complex ones
