# mr-kelly/far

FAR (File-Augmented Retrieval) skill for AI coding agents.

## Install

Recommended for multiple AI coding agents (via `npx skills`):

```
npx skills add mr-kelly/far
```

In Claude Code:

```
/plugin marketplace add mr-kelly/far
/plugin install mr-kelly-far
```

## Layout

- `.claude-plugin/marketplace.json` defines the marketplace and plugin.
- `skills/` contains skill folders (each with a `SKILL.md`).

## Skills

- `far` - File-Augmented Retrieval protocol for making binary files readable to AI agents.
