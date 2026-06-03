# Campsis Ascent Roadmap (April 2026)

## 1. Project Vision & Meaning

### Project Name: Campsis

Derived from the scientific name of the Chinese trumpet creeper (*Campsis grandiflora*), a climbing plant renowned for its tenacious vitality. It symbolizes:
- **Tenacity**: Thriving in all kinds of environments
- **Aspiration**: Constantly pursuing higher goals
- **Blooming Achievement**: Showcasing the most beautiful results at the peak
- **Sustainable Growth**: Boasting strong vitality for sustainable development

### Core Value Proposition
"Upward, Never Stop" - We believe that every piece of data has its value, every analysis can bring breakthroughs, and every progress is worth celebrating. Campsis is not just a tool, but a reliable partner on your journey of quantitative trading.

## 2. Project Overview

Campsis is an enterprise-grade data intelligence platform designed for individual quant traders and small teams (3-10 people). It adopts the "smart kitchen" metaphor to create a lightweight, user-friendly, full-process controlled quantitative trading system.

### Target Users
- Individual quantitative traders
- Small trading teams (3-10 people)
- Quantitative trading enthusiasts

### Core Pain Points Addressed
- Complex deployment and high costs of large institutional quant systems
- Fragmented tools (data download, backtesting, order execution)
- High entry barrier for non-professional developers
- Weak risk control awareness

## 3. Overall Development Goals

### Long-term Goals
- Build a complete quantitative trading ecosystem
- Provide end-to-end solutions from data acquisition to strategy execution
- Support both backtesting and live trading
- Establish a user-friendly strategy development environment

### Short-term Goals (Q2 2026)
- Complete data layer infrastructure
- Build basic backtesting engine
- Implement core strategy templates
- Develop simulation trading module

## 4. Development Timeline

### Timeframe
- **Start Date**: April 2026
- **Initial Release Target**: Q3 2026
- **Full Feature Completion**: Q4 2026

### Key Milestones

| Phase | Timeline | Milestone |
|-------|----------|-----------|
| Phase 1 | Apr 1-30, 2026 | Data Layer Completion |
| Phase 2 | May 1-31, 2026 | Backtesting Engine Implementation |
| Phase 3 | Jun 1-30, 2026 | Strategy Layer Development |
| Phase 4 | Jul 1-31, 2026 | Execution Layer Integration |
| Phase 5 | Aug 1-31, 2026 | User Interface Development |
| Phase 6 | Sep 1-15, 2026 | System Integration & Testing |
| Phase 7 | Sep 16-30, 2026 | Initial Release |

## 5. Architecture Overview

### 6-Layer Architecture

1. **Kitchen Base Layer** - System foundation (configuration, logging, exception handling)
2. **Ingredient Layer** - Data lifecycle management (data sources, cleaning, storage)
3. **Cooking Engine Layer** - Core engine capabilities (backtesting, risk control)
4. **Recipe R&D Layer** - Strategy development and verification
5. **Serving Layer** - Strategy execution (simulation/live trading)
6. **Dining Table Layer** - User interaction and result feedback

### Current Status
- ✅ Kitchen Base Layer: Basic completion
- 🔄 Ingredient Layer: Core development in progress
- ⏳ Cooking Engine Layer: To be developed
- ⏳ Recipe R&D Layer: To be developed
- ⏳ Serving Layer: To be developed
- ⏳ Dining Table Layer: To be developed

## 6. Development Plan by Phase

### Phase 1: Data Layer Completion (Apr 1-30, 2026)

**Priority: High**

| Task | Estimated Time | Description |
|------|----------------|-------------|
| K-Line Downloader Enhancement | 2-3 days | Support multiple timeframes (1min, 15min, 30min, 60min, daily) |
| Daily Data Incremental Update | 2-3 days | Implement daily automatic incremental update for daily data |
| Data Validation & Quality Monitoring | 3-4 days | Data integrity checks, anomaly detection, quality reporting |
| Database Optimization | 2 days | Index optimization, partition management |

### Phase 2: Backtesting Engine Implementation (May 1-31, 2026)

**Priority: High**

| Task | Estimated Time | Description |
|------|----------------|-------------|
| Backtesting Framework Architecture | 3-4 days | Define backtesting engine technical scheme |
| Basic Backtesting Engine | 5-7 days | Implement event-driven backtesting system |
| Performance Analytics Module | 3-4 days | Metrics calculation, risk assessment |
| Integration with Data Layer | 2-3 days | Connect backtesting engine with data sources |

### Phase 3: Strategy Layer Development (Jun 1-30, 2026)

**Priority: Medium**

| Task | Estimated Time | Description |
|------|----------------|-------------|
| Strategy Template Base Class | 2-3 days | Define standard strategy interfaces |
| Classic Strategy Implementation | 3-4 days | Moving average, MACD, RSI strategies |
| Strategy Parameter Optimization | 3-5 days | Parameter tuning framework |
| Strategy Testing & Validation | 2-3 days | Backtest strategy performance |

### Phase 4: Execution Layer Integration (Jul 1-31, 2026)

**Priority: Medium**

| Task | Estimated Time | Description |
|------|----------------|-------------|
| Simulation Trading Module | 3-5 days | Order simulation, execution confirmation, position management |
| Broker API Integration (Optional) | 5-7 days | Connect to real broker APIs |
| Risk Control System | 3-4 days | Position sizing, stop-loss mechanisms |
| Order Management System | 2-3 days | Order lifecycle management |

### Phase 5: User Interface Development (Aug 1-31, 2026)

**Priority: Low**

| Task | Estimated Time | Description |
|------|----------------|-------------|
| Command-Line Interface | 3-4 days | Basic CLI for system operations |
| Web Dashboard (Optional) | 7-10 days | Web-based visualization and control panel |
| Report Generation | 2-3 days | Performance reports, backtest results |
| User Configuration System | 2 days | User preferences and settings |

### Phase 6: System Integration & Testing (Sep 1-15, 2026)

**Priority: High**

| Task | Estimated Time | Description |
|------|----------------|-------------|
| End-to-End Integration | 3-4 days | Integrate all system components |
| Performance Testing | 2-3 days | System performance benchmarking |
| Stress Testing | 2-3 days | Test system under heavy load |
| Bug Fixing | 3-5 days | Address identified issues |

### Phase 7: Initial Release (Sep 16-30, 2026)

**Priority: High**

| Task | Estimated Time | Description |
|------|----------------|-------------|
| Documentation Completion | 3-4 days | User manuals, API docs |
| Deployment Preparation | 2-3 days | Installation scripts, setup guides |
| Release Testing | 2-3 days | Final verification |
| Initial Release | 1 day | Official release |

## 7. Technology Stack

| Category | Technology |
|----------|------------|
| Programming Language | Python 3.x |
| Database | MySQL + PyMySQL |
| Data Source | Baostock (Free A-share data) |
| Data Processing | Pandas |
| Logging System | Custom (based on logging) |
| SQL Templating | Jinja2 |
| Testing Framework | Pytest |
| Backtesting (Optional) | Backtrader or Custom |
| Web Framework (Optional) | Flask/FastAPI |

## 8. Key Features to Implement

### Data Layer
- Multi-timeframe K-line data download
- Incremental daily data updates
- Data quality monitoring
- Historical data management

### Backtesting Engine
- Event-driven backtesting
- Multiple performance metrics
- Risk assessment tools
- Strategy parameter optimization

### Strategy Layer
- Template-based strategy development
- Common technical indicator strategies
- Custom strategy support
- Strategy performance comparison

### Execution Layer
- Simulation trading
- Position management
- Risk control mechanisms
- Order execution tracking

### User Interface
- Command-line interface
- Performance visualization
- Strategy management
- Report generation

## 9. Success Metrics

### Technical Metrics
- Data download success rate > 99%
- Backtesting accuracy > 95%
- System response time < 1 second
- Data consistency across all timeframes

### Business Metrics
- Strategy development time reduction by 50%
- Backtesting efficiency improvement by 60%
- User adoption rate within target audience
- Positive user feedback score

## 10. Risk Management

### Technical Risks
- Data source reliability (Baostock API stability)
- System performance under large data volumes
- Broker API integration challenges
- Strategy overfitting

### Mitigation Strategies
- Multiple data source fallback mechanisms
- Database optimization and indexing
- Comprehensive error handling and logging
- Robust backtesting with out-of-sample validation

## 11. Conclusion

The Campsis Ascent Roadmap outlines a structured approach to building a comprehensive quantitative trading system. By focusing on data integrity, robust backtesting, and user-friendly design, we aim to create a platform that empowers individual traders and small teams to compete effectively in the A-share market.

With a clear development timeline and prioritized tasks, this roadmap provides a solid foundation for the successful implementation of the Campsis platform. The project's metaphor of upward growth aligns perfectly with our goal of creating a system that continuously evolves and improves alongside its users.

"Upward, Never Stop" - Let's begin the ascent!