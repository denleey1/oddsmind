# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OddsMind is a comprehensive football odds data collection and analysis system that:
- Scrapes match and odds data from titan007.com
- Stores data in MySQL database with optimized schema
- Provides real-time odds monitoring and analysis
- Offers a Flask-based API with web frontend for predictions
- Includes automated fundamental analysis calculations

## Commands

### Running the System

```bash
# Start API server with web interface (main entry point)
python run_api.py

# Run full prediction system with scheduled tasks
python prediction_system.py --mode full

# Run API server only
python prediction_system.py --mode api-only

# Windows quick start
run.bat

# Linux/Mac quick start
./run.sh
```

### Database Operations
```bash
# Initialize database and create tables
python main.py db-init

# Check database status
python main.py db-status

# Run database migrations
python alter_fundamental_table.sql  # Apply schema changes
```

### Data Collection
```bash
# Scrape league data
python main.py scrape-leagues --league-group big5  # Big 5 leagues
python main.py scrape-leagues --league-group all   # All configured leagues

# Scrape odds data with company filtering
python main.py scrape-odds --company-filter tier1   # Main companies only (791, 16, 680, 649, 104)
python main.py scrape-odds --company-filter all     # All companies

# Full pipeline
python main.py full-pipeline --league-group big5 --company-filter tier1
```

### Testing and Validation
```bash
# Test fundamental analysis
python test_fundamental_complete.py

# Validate odds analysis
python validation_test/debug_validator.py

# Generate analysis report
python validation_test/generate_md_report.py
```

## High-Level Architecture

### Service Layer Architecture
```
run_api.py / prediction_system.py (Entry Points)
├── services/
│   ├── prediction_api.py (Flask app factory, API routes)
│   ├── comprehensive_analyzer.py (Match analysis orchestrator)
│   ├── odds_monitor.py (Real-time odds monitoring)
│   ├── auto_fundamental_service.py (Automated analysis)
│   └── api/
│       ├── analysis.py (Analysis endpoints)
│       ├── monitoring.py (Monitor control endpoints)
│       ├── data.py (Data query endpoints)
│       └── system.py (System control endpoints)
```

### Data Processing Pipeline
1. **Data Collection**: `scrapers/` → titan007.com data
2. **Storage**: `database/repository.py` → MySQL with connection pooling
3. **Analysis**: 
   - `fundamental_analysis/` → Basic match analysis
   - `odds_analysis/` → Odds pattern analysis
   - `calculation/` → Mathematical models
4. **API Layer**: Flask endpoints serve processed data
5. **Frontend**: `templates/index.html` + `static/main.js`

### Key Database Tables
- `fundamental_analysis`: 7-level confidence classifications with betting patterns
- `odds_analysis_results`: Company-specific predictions with rule values
- `matches`, `teams`, `leagues`: Core match data
- `european_odds`: Historical odds data
- `companies`: Betting company information

### Important Configuration

#### Main Companies (Tier 1)
The system focuses on 5 main betting companies:
- 791: Sisa*(意大利)
- 16: 10*(英国) 
- 680: Stanley*(马尔他)
- 649: IBC*(哥斯达黎加)
- 104: Interwet*(塞浦路斯)

#### Confidence Classification System
7-level system stored in `fundamental_analysis` table:
- 欠缺信心 (0.0-1.3)
- 信心不足 (1.4-2.7)
- 信心中下 (2.8-4.1)
- 信心中庸 (4.2-6.7)
- 信心中上 (6.8-7.8)
- 信心充足 (7.9-8.9)
- 极致信心 (9.0-10.0)

### API Endpoints

Key endpoints exposed by the Flask app:
- `GET /api/analyze/<match_id>` - Get match analysis with company predictions
- `POST /api/monitor/start/<match_id>` - Start odds monitoring
- `GET /api/matches/recent` - Get recent matches
- `GET /api/fundamental/trigger` - Trigger fundamental analysis
- `GET /api/odds_analysis/<match_id>` - Get detailed odds analysis

### Frontend Integration

The web interface expects:
- `match.company_predictions[]` - Array of company predictions
- `match.fundamental_analysis` - 7-level confidence data
- Each company prediction includes `initial` and `current` analysis

### Performance Optimizations
- Database connection pooling (20 connections)
- Batch operations via `optimized_repository.py`
- Concurrent scraping with ThreadPoolExecutor (max_workers=10)
- Rate limiting to avoid overwhelming data sources

### Testing Data
- Use match ID "2702235" for reliable testing
- Company IDs 791, 16, 680, 649, 104 have comprehensive data
- Database stores pre-calculated fundamental analysis

### Common Development Tasks

When adding new analysis features:
1. Update `services/auto_fundamental_service.py` for data storage
2. Modify API endpoints in `services/prediction_api.py`
3. Update frontend in `static/main.js` to display new data

When debugging frontend display issues:
1. Check browser console for JavaScript errors
2. Verify API response format matches frontend expectations
3. Ensure functions are exposed to global scope (`window.functionName = functionName`)

When modifying database schema:
1. Update schema in `database/database_config.py`
2. Create migration SQL in project root
3. Update repository classes in `database/`