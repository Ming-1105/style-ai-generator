# Project instructions

## Project
Build an AI-powered style analysis and generation app for IDEM307.
Use the Vorden mockup as the source for style data. Do not invent Vorden traits; mark unknown details as TODO.

## First user flow
1. Select a target style.
2. Upload or select a design image.
3. See a style comparison and suggestions.

## Draft data formats
Confirm these formats together before implementation.

A style package contains:
- `style_id`
- `name`
- `traits`: each trait has `trait_id`, `name`, `category`, `description`, and `weight`

A comparison result contains:
- `style_id`
- `overall_score` (0 to 1)
- `trait_scores`: each has `trait_id`, `score` (0 to 1), and `explanation`
- `suggestions`: a list of suggestions

## Module ownership
- `sourcing/`: find image candidates, remove duplicates, flag doubtful images
- `ai-core/`: extract style traits, calculate fit scores, generate suggestions
- `interface/`: build the user interface; use fake JSON data first
- `data/`: shared example JSON data

## Collaboration
- Work on separate branches and keep changes small.
- Keep each part's files in its assigned folder.
- Discuss changes to shared data formats before implementing them.

## Secrets
- Keep API keys in a local `.env` file.
- Never commit `.env`; use `.env.example` with empty values.
