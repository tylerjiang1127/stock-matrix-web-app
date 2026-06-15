import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { createChart, ColorType, CrosshairMode } from 'lightweight-charts';
import axios from 'axios';
import './StockChart.css';

const StockChart = () => {
    // three chart containers references
    const priceChartRef = useRef();
    const volumeChartRef = useRef();
    const technicalChartRef = useRef();
    
    // three independent chart instances
    const priceChart = useRef();
    const volumeChart = useRef();
    const technicalChart = useRef();
    
    // series references
    const candlestickSeries = useRef();
    const volumeSeries = useRef();
    const maSeries = useRef({});
    const technicalSeries = useRef({});
    
    // sync control flags
    const syncInProgress = useRef(false);
    const crosshairSyncInProgress = useRef(false);
    
    // store all charts references for sync
    const allCharts = useRef([]);
    
    // vertical indicator line references
    const verticalLineRefs = useRef([]);
    
    const [stockData, setStockData] = useState(null);
    const [loading, setLoading] = useState(false); // Global loading (Ticker changes only)
    const [chartLoading, setChartLoading] = useState(false); // Chart loading (Interval changes)
    const [maLoading, setMaLoading] = useState(false); // MA specific loading
    const [techLoading, setTechLoading] = useState(false); // Tech specific loading
    const [fundamentalLoading, setFundamentalLoading] = useState(false); // Fundamental data loading
    const [error, setError] = useState(null);
    const [crosshairData, setCrosshairData] = useState({
        price: null,
        volume: null,
        technical: null
    }); // store crosshair position data
    const [currentTime, setCurrentTime] = useState(null); // store current mouse position time
    const [highlightedMA, setHighlightedMA] = useState(null);
    
    // Stock list for search functionality
    const [stockList, setStockList] = useState([]);
    const [filteredStocks, setFilteredStocks] = useState([]);
    const [showStockSuggestions, setShowStockSuggestions] = useState(false);
    
    // Separate state for search inputs (Form State)
    const [searchParams, setSearchParams] = useState({
        ticker: 'AAPL',
        interval: '1d',
        ma_options: 'sma',
        tech_ind: 'macd'
    });

    // Active chart configuration (Dashboard State) - updated only on search
    const [chartConfig, setChartConfig] = useState({
        ticker: 'AAPL',
        interval: '1d',
        ma_options: 'sma',
        tech_ind: 'macd'
    });

    // Store time ranges from backend
    const [timeRanges, setTimeRanges] = useState([]);
    
    // Fundamental data period selection
    const [fundamentalPeriod, setFundamentalPeriod] = useState('Quarterly'); // 'Quarterly' or 'Yearly'
    
    // Memoize fundamental data processing to avoid recalculation on every render
    const processedFundamentalData = useMemo(() => {
        if (!stockData?.fundamental_data) return null;
        
        const periodKey = fundamentalPeriod === 'Yearly' ? 'annual' : 'quarterly';
        const periodData = stockData.fundamental_data[periodKey] || {};
        
        // Handle both MongoDB format (with 'data' key) and API format (direct DataFrame-like structure)
        let incomeData = [];
        let balanceData = [];
        let cashFlowData = [];
        
        // Process income statement
        const incomeStatement = periodData.income_statement || {};
        if (incomeStatement && incomeStatement.data && Array.isArray(incomeStatement.data)) {
            incomeData = incomeStatement.data;
        } else if (Array.isArray(incomeStatement)) {
            incomeData = incomeStatement;
        }
        
        // Process balance sheet
        const balanceSheet = periodData.balance_sheet || {};
        if (balanceSheet && balanceSheet.data && Array.isArray(balanceSheet.data)) {
            balanceData = balanceSheet.data;
        } else if (Array.isArray(balanceSheet)) {
            balanceData = balanceSheet;
        }
        
        // Process cash flow
        const cashFlow = periodData.cash_flow || {};
        if (cashFlow && cashFlow.data && Array.isArray(cashFlow.data)) {
            cashFlowData = cashFlow.data;
        } else if (Array.isArray(cashFlow)) {
            cashFlowData = cashFlow;
        }
        
        if (incomeData.length === 0 && balanceData.length === 0 && cashFlowData.length === 0) {
            return null;
        }
        
        // Helper function to get value with field name mapping
        const getFieldValue = (record, fieldName, camelCaseName) => {
            if (record[fieldName] !== undefined) return record[fieldName];
            if (record[camelCaseName] !== undefined) return record[camelCaseName];
            return null;
        };
        
        // Get most recent period data
        const mostRecentIncome = incomeData[0] || {};
        const mostRecentBalance = balanceData[0] || {};
        const mostRecentCashFlow = cashFlowData[0] || {};
        const reportDate = mostRecentIncome.fiscalDateEnding || mostRecentBalance.fiscalDateEnding || mostRecentCashFlow.fiscalDateEnding || 'N/A';
        
        // Format report date
        let formattedReportDate = reportDate;
        if (reportDate && reportDate !== 'N/A') {
            try {
                if (typeof reportDate === 'string' && reportDate.includes('T')) {
                    formattedReportDate = reportDate.split('T')[0];
                } else if (typeof reportDate === 'string') {
                    formattedReportDate = reportDate;
                } else {
                    formattedReportDate = reportDate.toString().split('T')[0];
                }
            } catch (e) {
                formattedReportDate = reportDate;
            }
        }
        
        // Create mapped objects with both field name formats for easy access
        const totalRevenue = getFieldValue(mostRecentIncome, 'Total Revenue', 'totalRevenue');
        const netIncome = getFieldValue(mostRecentIncome, 'Net Income', 'netIncome');
        
        // Calculate Net Profit Margin if not available
        let netProfitMargin = getFieldValue(mostRecentIncome, 'Net Profit Margin', 'netProfitMargin');
        if (netProfitMargin === null && totalRevenue != null && netIncome != null && totalRevenue !== 0) {
            netProfitMargin = netIncome / totalRevenue;
        }
        
        const incomeMapped = {
            'Total Revenue': totalRevenue,
            'Cost Of Revenue': getFieldValue(mostRecentIncome, 'Cost Of Revenue', 'costOfRevenue'),
            'Gross Profit': getFieldValue(mostRecentIncome, 'Gross Profit', 'grossProfit'),
            'Operating Income': getFieldValue(mostRecentIncome, 'Operating Income', 'operatingIncome'),
            'Net Income': netIncome,
            'Net Profit Margin': netProfitMargin
        };
        
        const balanceMapped = {
            'Total Assets': getFieldValue(mostRecentBalance, 'Total Assets', 'totalAssets'),
            'Total Liab': getFieldValue(mostRecentBalance, 'Total Liab', 'totalLiabilities') || getFieldValue(mostRecentBalance, 'Total Liabilities', 'totalLiabilities'),
            'Total Stockholder Equity': getFieldValue(mostRecentBalance, 'Total Stockholder Equity', 'totalShareholderEquity'),
            'Cash': getFieldValue(mostRecentBalance, 'Cash', 'cashAndCashEquivalentsAtCarryingValue'),
            'Total Current Assets': getFieldValue(mostRecentBalance, 'Total Current Assets', 'totalCurrentAssets'),
            'Total Current Liabilities': getFieldValue(mostRecentBalance, 'Total Current Liabilities', 'totalCurrentLiabilities')
        };
        
        // Calculate Free Cash Flow if not available: Operating CF + Capital Expenditures (CapEx is usually negative)
        const operatingCF = getFieldValue(mostRecentCashFlow, 'Total Cash From Operating Activities', 'operatingCashflow');
        const capitalExpenditures = getFieldValue(mostRecentCashFlow, 'Capital Expenditures', 'capitalExpenditures');
        let freeCashFlow = getFieldValue(mostRecentCashFlow, 'Free Cash Flow', 'freeCashFlow');
        if (freeCashFlow === null && operatingCF != null) {
            // CapEx is usually negative, so we add it (subtract the absolute value)
            const capExValue = capitalExpenditures != null ? parseFloat(capitalExpenditures) : 0;
            freeCashFlow = parseFloat(operatingCF) + capExValue; // Adding because CapEx is negative
        }
        
        const cashFlowMapped = {
            'Total Cash From Operating Activities': operatingCF,
            'Total Cashflows From Investing Activities': getFieldValue(mostRecentCashFlow, 'Total Cashflows From Investing Activities', 'cashflowFromInvestment'),
            'Total Cash From Financing Activities': getFieldValue(mostRecentCashFlow, 'Total Cash From Financing Activities', 'cashflowFromFinancing'),
            'Capital Expenditures': capitalExpenditures,
            'Free Cash Flow': freeCashFlow
        };
        
        return {
            incomeData,
            balanceData,
            cashFlowData,
            incomeMapped,
            balanceMapped,
            cashFlowMapped,
            formattedReportDate
        };
    }, [stockData?.fundamental_data, fundamentalPeriod]);

    // Performance Optimization: Create an indexed data structure for fast lookups (O(1))
    // This avoids iterating through arrays on every mouse move (O(N))
    const indexedStockData = React.useMemo(() => {
        if (!stockData) return null;

        const index = new Map();
        
        // Helper to add data to index
        const addToIndex = (dataArray, category, subKey = null, valueProcessor = null) => {
            if (!Array.isArray(dataArray)) return;
            
            dataArray.forEach(item => {
                if (!item || item.time === undefined) return;
                
                if (!index.has(item.time)) {
                    index.set(item.time, {
                        candlestick: null,
                        volume: null,
                        ma: {},
                        technical: {}
                    });
                }
                
                const timeSlot = index.get(item.time);
                
                if (category === 'candlestick') {
                    timeSlot.candlestick = item;
                } else if (category === 'volume') {
                    timeSlot.volume = item;
                } else if (category === 'ma') {
                    // For MAs, we construct the key like SMA5, EMA20
                    // The item usually has a 'period' field
                    if (subKey && item.period) {
                        const key = `${subKey.toUpperCase()}${item.period}`;
                        timeSlot.ma[key] = item;
                    } else if (subKey) {
                        // Fallback for Bollinger Bands which don't have periods in the same way
                        timeSlot.ma[subKey] = item;
                    }
                } else if (category === 'technical') {
                    if (subKey) {
                        timeSlot.technical[subKey] = item;
                    }
                }
            });
        };

        // 1. Index Candlestick Data
        addToIndex(stockData.candlestick_data, 'candlestick');
        
        // 2. Index Volume Data
        addToIndex(stockData.volume_data, 'volume');
        
        // 3. Index Moving Average Data
        if (stockData.ma_data) {
            Object.entries(stockData.ma_data).forEach(([type, data]) => {
                if (type === 'bbands_upper') {
                    addToIndex(data, 'ma', 'BBANDS_UPPER');
                } else if (type === 'bbands_lower') {
                    addToIndex(data, 'ma', 'BBANDS_LOWER');
                } else {
                    // sma, ema, etc.
                    addToIndex(data, 'ma', type);
                }
            });
        }
        
        // 4. Index Technical Data
        if (stockData.technical_data) {
            Object.entries(stockData.technical_data).forEach(([key, data]) => {
                addToIndex(data, 'technical', key);
            });
        }
        
        return index;
    }, [stockData]);

    // base chart config
    const getBaseChartConfig = (height) => ({
        layout: {
            background: { type: ColorType.Solid, color: 'white' },
            textColor: 'black',
            fontFamily: 'Raleway, sans-serif',
            fontSize: 12,
        },
        grid: {
            vertLines: { visible: false },
            horzLines: { visible: false },
        },
        crosshair: {
            mode: CrosshairMode.Normal,
            vertLine: { 
                color: 'rgba(0, 0, 0, 0.5)', 
                width: 1, 
                style: 0,
                labelVisible: true
            },
            horzLine: { 
                color: 'rgba(0, 0, 0, 0.5)', 
                width: 1, 
                style: 0,
                labelVisible: true
            },
        },
        rightPriceScale: {
            borderColor: 'rgba(197, 203, 206, 1)',
            scaleMargins: {
                top: 0.1,
                bottom: 0.1,
            },
            width: 80, // Fixed width for horizontal alignment across stacked charts
        },
        timeScale: {
            borderColor: 'rgba(197, 203, 206, 1)',
            timeVisible: true,
            secondsVisible: false,
            fixLeftEdge: true,
            fixRightEdge: true,
            rightOffset: 0, // Ensure same right edge alignment across stacked charts
            barSpacing: 6, // Fixed bar spacing for alignment
        },
        height: height,
    });

    // create vertical indicator line
    const createVerticalLine = (container, chartIndex) => {
        const line = document.createElement('div');
        line.style.cssText = `
            position: absolute;
            top: 0;
            bottom: 0;
            width: 1px;
            background: rgba(0, 0, 0, 0.5);
            border-left: 1px dashed rgba(0, 0, 0, 0.7);
            z-index: 10;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s ease;
        `;
        container.appendChild(line);
        verticalLineRefs.current[chartIndex] = line;
        return line;
    };
    
    // update all vertical lines positions
    const updateVerticalLines = (time) => {
        if (!time) {
            // hide all vertical lines
            verticalLineRefs.current.forEach(line => {
                if (line) line.style.opacity = '0';
            });
            return;
        }
        
        allCharts.current.forEach((chart, index) => {
            const line = verticalLineRefs.current[index];
            if (chart && line) {
                try {
                    const coordinate = chart.timeScale().timeToCoordinate(time);
                    if (coordinate !== null && coordinate >= 0) {
                        line.style.left = `${coordinate}px`;
                        line.style.opacity = '0.7';
                    } else {
                        line.style.opacity = '0';
                    }
                } catch (error) {
                    line.style.opacity = '0';
                }
            }
        });
    };

    // simplified crosshair sync function - temporarily disable complex DOM event sync
    const syncCrosshair = (sourceChart, param) => {
        // temporarily disable crosshair sync, because Lightweight Charts API limit
        // focus on time axis sync, this is more important
        return;
    };

    // safe time axis sync function
    const syncTimeScale = (sourceChart, visibleRange) => {
        if (syncInProgress.current) return;
        
        syncInProgress.current = true;
        
        try {
            // Fixed validation logic - properly check for null/undefined (not falsy values like 0)
            if (!visibleRange || 
                visibleRange.from == null ||
                visibleRange.to == null ||
                visibleRange.from === visibleRange.to) {
                return;
            }
            
            allCharts.current.forEach((chart, index) => {
                if (chart && chart !== sourceChart && chart.timeScale) {
                    try {
                        const timeScale = chart.timeScale();
                        if (timeScale && typeof timeScale.setVisibleRange === 'function') {
                            const currentRange = timeScale.getVisibleLogicalRange();
                            if (currentRange == null) return; // Chart has no data yet
                            timeScale.setVisibleRange(visibleRange);
                        }
                    } catch (error) {
                        // Silently handle sync errors
                    }
                }
            });
        } finally {
                syncInProgress.current = false;
        }
    };

    // initialize three charts
    useEffect(() => {
        let charts = [];
        
        try {
            // initialize price chart
            if (priceChartRef.current) {
                // Height 378 = 350 (visible) + 28 (timeScale, hidden by CSS overflow)
                // This ensures price chart has same internal layout as volume chart
                priceChart.current = createChart(priceChartRef.current, {
                    ...getBaseChartConfig(378),
                    width: priceChartRef.current.clientWidth,
                    timeScale: {
                        ...getBaseChartConfig(378).timeScale, // Inherit base timeScale config
                        visible: true, // Keep visible for layout alignment with volume chart
                    },
                    leftPriceScale: {
                        visible: false,
                    },
                });

                candlestickSeries.current = priceChart.current.addCandlestickSeries({
                    upColor: '#26a69a',
                    downColor: '#ef5350',
                    borderVisible: false,
                    wickUpColor: '#26a69a',
                    wickDownColor: '#ef5350',
                priceFormat: {
                    type: 'price',
                    precision: 2,
                    minMove: 0.01,
                },
                priceLineVisible: false,
                lastValueVisible: false,
                });
                
                charts.push(priceChart.current);
                
                // create vertical indicator line
                createVerticalLine(priceChartRef.current, 0);
            }

            // initialize volume chart
            if (volumeChartRef.current) {
                // Use same width as price chart for alignment
                const volumeChartWidth = priceChartRef.current?.clientWidth || volumeChartRef.current.clientWidth;
                
                volumeChart.current = createChart(volumeChartRef.current, {
                    ...getBaseChartConfig(120),
                    width: volumeChartWidth,
                    timeScale: {
                        ...getBaseChartConfig(120).timeScale,
                    },
                    leftPriceScale: {
                        visible: false,
                    },
                });

                volumeSeries.current = volumeChart.current.addHistogramSeries({
                    color: '#26a69a',
                    priceFormat: { type: 'volume' },
                    priceLineVisible: false,
                    lastValueVisible: false,
                });
                
                charts.push(volumeChart.current);
                
                // create vertical indicator line
                createVerticalLine(volumeChartRef.current, 1);
            }

            // initialize technical indicators chart
            if (technicalChartRef.current) {
                technicalChart.current = createChart(technicalChartRef.current, {
                    ...getBaseChartConfig(200),
                    width: technicalChartRef.current.clientWidth,
                });
                
                charts.push(technicalChart.current);
                
                // create vertical indicator line
                createVerticalLine(technicalChartRef.current, 2);
            }

            // set chart sync (delay execution, ensure all charts are initialized)
            setTimeout(() => {
                const validCharts = charts.filter(Boolean);
                allCharts.current = validCharts; // store all charts references
                
                validCharts.forEach((chart, index) => {
                    if (chart && chart.timeScale) {
                        // time axis sync
                        chart.timeScale().subscribeVisibleTimeRangeChange((visibleRange) => {
                            syncTimeScale(chart, visibleRange);
                        });
                        

                    }
                });
            }, 100);

            // Function to remove watermark elements - target the specific ID
            const removeWatermark = () => {
                // Method 1: Directly target the ID (most reliable)
                const logoElement = document.getElementById('tv-attr-logo');
                if (logoElement) {
                    logoElement.style.display = 'none';
                    logoElement.style.visibility = 'hidden';
                    logoElement.style.opacity = '0';
                    logoElement.style.height = '0';
                    logoElement.style.width = '0';
                    logoElement.style.pointerEvents = 'none';
                }

                // Method 2: Search in chart containers
                const containers = [
                    priceChartRef.current,
                    volumeChartRef.current,
                    technicalChartRef.current
                ].filter(Boolean);

                containers.forEach(container => {
                    if (!container) return;
                    
                    // Find by ID within container
                    const logo = container.querySelector('#tv-attr-logo');
                    if (logo) {
                        logo.style.display = 'none';
                        logo.style.visibility = 'hidden';
                        logo.style.opacity = '0';
                    }

                    // Also find by class name as backup
                    const watermarks = container.querySelectorAll('[class*="watermark"], [class*="Watermark"]');
                    watermarks.forEach(el => {
                        el.style.display = 'none';
                        el.style.visibility = 'hidden';
                    });
                });
            };

            // Try to remove watermark multiple times (charts render asynchronously)
            setTimeout(removeWatermark, 100);
            setTimeout(removeWatermark, 300);
            setTimeout(removeWatermark, 500);
            setTimeout(removeWatermark, 1000);
            setTimeout(removeWatermark, 2000);

            // Use MutationObserver to catch dynamically added watermarks
            const containers = [
                priceChartRef.current,
                volumeChartRef.current,
                technicalChartRef.current
            ].filter(Boolean);

            const observer = new MutationObserver(() => {
                removeWatermark();
            });

            containers.forEach(container => {
                if (container) {
                    observer.observe(container, {
                        childList: true,
                        subtree: true,
                        attributes: true,
                        attributeFilter: ['class', 'style']
                    });
                }
            });

        } catch (error) {
            console.error('Error initializing charts:', error);
        }

        // window size adjustment handling
        const handleResize = () => {
            // Use price chart width as reference for volume chart to ensure alignment
            const priceWidth = priceChartRef.current?.clientWidth;
            
            if (priceChart.current && priceChartRef.current) {
                try {
                    priceChart.current.applyOptions({ width: priceWidth });
                    } catch (error) {
                    console.warn('Error resizing price chart:', error);
                }
            }
            
            // Volume chart uses same width as price chart for alignment
            if (volumeChart.current && volumeChartRef.current && priceWidth) {
                try {
                    volumeChart.current.applyOptions({ width: priceWidth });
                } catch (error) {
                    console.warn('Error resizing volume chart:', error);
                }
            }
            
            // Technical chart uses its own container width
            if (technicalChart.current && technicalChartRef.current) {
                try {
                    technicalChart.current.applyOptions({ width: technicalChartRef.current.clientWidth });
                } catch (error) {
                    console.warn('Error resizing technical chart:', error);
                }
            }
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            
            // clean up chart instances
            [priceChart.current, volumeChart.current, technicalChart.current].forEach(chart => {
                if (chart) {
                    try {
                        chart.remove();
                    } catch (error) {
                        console.warn('Error removing chart:', error);
                    }
                }
            });
        };
    }, []);

    // get stock data
    // Fetch stock list from MongoDB
    const fetchStockList = async () => {
        try {
            const response = await axios.get('http://localhost:8000/api/stocks');
            setStockList(response.data);
        } catch (err) {
            console.error('Failed to fetch stock list:', err);
        }
    };

    // Filter stocks based on input
    const filterStocks = (input) => {
        if (!input || input.length < 1) {
            setFilteredStocks([]);
            setShowStockSuggestions(false);
            return;
        }
        
        const filtered = stockList.filter(stock => 
            stock.symbol.toLowerCase().includes(input.toLowerCase()) ||
            stock.name.toLowerCase().includes(input.toLowerCase())
        ).slice(0, 10); // Limit to 10 suggestions
        
        setFilteredStocks(filtered);
        setShowStockSuggestions(true);
    };

    // Fetch stock data from PostgreSQL
    const fetchStockData = async (overrideParams = {}, loadingScope = 'global') => {
        // Set specific loading state based on scope
        if (loadingScope === 'ma') {
            setMaLoading(true);
        } else if (loadingScope === 'tech') {
            setTechLoading(true);
        } else if (loadingScope === 'charts') {
            setChartLoading(true); // Chart data only (interval changes)
        } else {
            setLoading(true); // global (Ticker changes only - includes company info)
            setFundamentalLoading(true); // Also load fundamental data when ticker changes
        }
        
        setError(null);
        
        // Use override params if provided, otherwise use current searchParams
        // This allows immediate fetching before state updates propagate
        const params = {
            ticker: overrideParams.ticker || searchParams.ticker,
            interval: overrideParams.interval || searchParams.interval,
            ma_options: overrideParams.ma_options !== undefined ? overrideParams.ma_options : searchParams.ma_options,
            tech_ind: overrideParams.tech_ind !== undefined ? overrideParams.tech_ind : searchParams.tech_ind
        };

        try {
            const response = await axios.post('http://localhost:8000/api/stocks/' + params.ticker, {
                interval: params.interval,
                ma_options: params.ma_options,
                tech_ind: params.tech_ind
            });
            
            // Update the active chart configuration
            // Merge current config with new params to ensure consistency
            setChartConfig(prev => ({
                ...prev,
                ...params
            }));
            
            // Also update searchParams to keep them in sync with what's displayed
            setSearchParams(prev => ({
                ...prev,
                ...params
            }));

            setStockData(response.data);
            
            // Extract and store time ranges from chart_config
            if (response.data.chart_config && response.data.chart_config.time_ranges) {
                setTimeRanges(response.data.chart_config.time_ranges);
            }
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to fetch stock data');
        } finally {
            // Reset all loading states
            setLoading(false);
            setChartLoading(false);
            setMaLoading(false);
            setTechLoading(false);
            setFundamentalLoading(false);
        }
    };

    // Handle immediate changes for Interval, MA, and Tech Ind
    // Updates state AND triggers fetch immediately
    const handleImmediateChange = (key, value) => {
        // 1. Update form state
        setSearchParams(prev => ({
            ...prev,
            [key]: value
        }));

        // 2. Determine loading scope
        let scope = 'charts'; // Default to charts scope (interval changes)
        if (key === 'ma_options') scope = 'ma';
        if (key === 'tech_ind') scope = 'tech';
        // Note: interval changes use 'charts' scope to avoid reloading company info

        // 3. Trigger fetch immediately with new value
        fetchStockData({ [key]: value }, scope);
    };

    // Initial data fetch
    useEffect(() => {
        fetchStockList(); // Load stock list first
        fetchStockData();
    }, []);

    // completely rebuild event binding logic 
    useEffect(() => {
        if (!stockData) return;
        
        // 1. First update the chart data
            updateCharts();
        
        // 2. Then bind events (delay to ensure the chart is updated)
        setTimeout(() => {
            const charts = [priceChart.current, volumeChart.current, technicalChart.current];
            
            charts.forEach((chart, index) => {
                if (!chart) return;
                
                let isMounted = true;
                
                const handleCrosshairMove = (param) => {
                    if (!isMounted) return;
                    
                    // update vertical indicator line
                    updateVerticalLines(param.time);
                    
                    // Sync crosshair between price and volume charts for shared x-axis
                    // When hovering price chart (index 0), show crosshair on volume chart
                    if (index === 0 && volumeChart.current && volumeSeries.current) {
                        if (param.time && param.point) {
                            // Set crosshair on volume chart to show date label on shared x-axis
                            try {
                                volumeChart.current.setCrosshairPosition(0, param.time, volumeSeries.current);
                            } catch (e) {
                                // Ignore errors if crosshair can't be set
                            }
                        } else {
                            try {
                                volumeChart.current.clearCrosshairPosition();
                            } catch (e) {
                                // Ignore
                            }
                        }
                    }
                    
                    // When hovering volume chart (index 1), sync to price chart for vertical line alignment
                    if (index === 1 && priceChart.current && candlestickSeries.current) {
                        if (param.time && param.point) {
                            try {
                                priceChart.current.setCrosshairPosition(0, param.time, candlestickSeries.current);
                            } catch (e) {
                                // Ignore
                            }
                        } else {
                            try {
                                priceChart.current.clearCrosshairPosition();
                            } catch (e) {
                                // Ignore
                            }
                        }
                    }
                    
                    // update current time state
                    if (param.time) {
                        setCurrentTime(param.time);
                    } else {
                        setCurrentTime(null);
                    }
                    
                    // new: detect closest MA line (only calculate MA lines, exclude Bollinger Bands)
                    if (param.time && param.seriesData && stockData && index === 0 && param.point) {

                        const chartRect = priceChartRef.current.getBoundingClientRect();
                        const isMouseInChart = param.point.x >= 0 && param.point.x <= chartRect.width && 
                                              param.point.y >= 0 && param.point.y <= chartRect.height;

                        
                        if (isMouseInChart) {
                            let closestMA = null;
                            let minDistance = Infinity;
                            
                            Object.entries(maSeries.current).forEach(([name, series]) => {
                                // only process MA lines, exclude Bollinger Bands
                                if ((name.includes('MA') || name.includes('EMA') || name.includes('WMA')) && 
                                    series && param.seriesData.has(series)) {
                                    const maData = param.seriesData.get(series);
                                    
                                    if (maData && maData.value !== undefined) {
                                        // use coordinateToPrice method to convert mouse Y coordinate to price value
                                        const mousePrice = series.coordinateToPrice(param.point.y);
                                        
                                        if (mousePrice !== null) {
                                            // calculate difference between MA price value and mouse position price value
                                            const distance = Math.abs(maData.value - mousePrice);
                                            
                                            if (distance < minDistance) {
                                                minDistance = distance;
                                                closestMA = name;
                                            }
                                        }
                                    }
                                }
                            });
                            
                            // set price difference threshold
                            const threshold = 2.0; // 价格差异阈值，可以调整
                            const newHighlightedMA = minDistance <= threshold ? closestMA : null;
                            
                            // only update state when value really changes
                            if (newHighlightedMA !== highlightedMA) {
                                setHighlightedMA(newHighlightedMA);
                            }
                        } else {
                            // mouse is not in chart area, clear highlight
                            if (highlightedMA !== null) {
                                setHighlightedMA(null);
                            }
                        }
                    } else if (!param.time || !param.point) {
                        if (highlightedMA !== null) {
                            setHighlightedMA(null);
                        }
                    }
                    
                    // Unified handling of all chart data updates
                    if (param.time && param.seriesData && stockData) {
                        updateAllChartsData(param.time, index, param.seriesData);
                    } else {
                        setCrosshairData({
                            price: null,
                            volume: null,
                            technical: null
                        });
                    }
                };
                
                chart.subscribeCrosshairMove(handleCrosshairMove);
                
                // Return cleanup function
                return () => {
                    isMounted = false;
                    // Note: Lightweight Charts does not have an unsubscribeCrosshairMove method
                    // So here we can only set the flag
                };
            });
            
        }, 150);
        
    }, [stockData]); // remove highlightedMA dependency

// add this useEffect to dynamically update MA line styles
useEffect(() => {
    if (!maSeries.current) return;
    
    // traverse all MA lines, update their styles
    Object.entries(maSeries.current).forEach(([name, series]) => {
        if (name.includes('MA') || name.includes('EMA') || name.includes('WMA')) {
            const isHighlighted = highlightedMA === name;
            
            // dynamically update line styles
            series.applyOptions({
                lineWidth: isHighlighted ? 3 : 1,
                lastValueVisible: false, 
            });
        }
    });
}, [highlightedMA]); // when highlightedMA changes

// Render trend charts for fundamental data
useEffect(() => {
    if (!processedFundamentalData) return;
    
    const { incomeData, balanceData, cashFlowData } = processedFundamentalData;
    
    // Helper function to format financial values (for use in useEffect)
    const formatFinancialValueForChart = (value) => {
        if (value === null || value === undefined || value === '' || value === 'None') return 'N/A';
        const numValue = typeof value === 'string' ? parseFloat(value) : value;
        if (isNaN(numValue)) return 'N/A';
        if (Math.abs(numValue) >= 1e9) return `$${(numValue / 1e9).toFixed(2)}B`;
        if (Math.abs(numValue) >= 1e6) return `$${(numValue / 1e6).toFixed(2)}M`;
        if (Math.abs(numValue) >= 1e3) return `$${(numValue / 1e3).toFixed(2)}K`;
        return `$${numValue.toFixed(2)}`;
    };
    
    // Helper to render a line chart with legend and hover interaction
    const renderTrendChart = (containerId, data, labels, title, colors) => {
        const container = document.getElementById(containerId);
        if (!container || !data || data.length === 0) return;
        
        // Clear previous content
        container.innerHTML = '';
        
        // Create wrapper for chart and legend
        const wrapper = document.createElement('div');
        wrapper.style.position = 'relative';
        wrapper.style.width = '100%';
        wrapper.style.height = '100%';
        
        // Create canvas for chart
        const canvas = document.createElement('canvas');
        // Canvas width will be adjusted based on available space (container width minus legend width)
        canvas.width = container.clientWidth - 150; // Reserve space for legend on right
        canvas.height = container.clientHeight - 20;
        canvas.style.cursor = 'crosshair';
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        
        // Create chart container with flex layout
        const chartContainer = document.createElement('div');
        chartContainer.style.display = 'flex';
        chartContainer.style.width = '100%';
        chartContainer.style.height = '100%';
        chartContainer.style.gap = '15px';
        
        // Create legend container (right side)
        const legendContainer = document.createElement('div');
        legendContainer.style.display = 'flex';
        legendContainer.style.flexDirection = 'column';
        legendContainer.style.justifyContent = 'flex-start';
        legendContainer.style.gap = '10px';
        legendContainer.style.padding = '10px';
        legendContainer.style.minWidth = '120px';
        legendContainer.style.flexShrink = 0;
        
        data.forEach((series, idx) => {
            const legendItem = document.createElement('div');
            legendItem.style.display = 'flex';
            legendItem.style.alignItems = 'center';
            legendItem.style.gap = '8px';
            legendItem.style.fontSize = '11px';
            legendItem.style.color = '#333';
            
            const colorBox = document.createElement('div');
            colorBox.style.width = '12px';
            colorBox.style.height = '12px';
            colorBox.style.backgroundColor = colors[idx] || '#4dabf7';
            colorBox.style.borderRadius = '2px';
            colorBox.style.flexShrink = 0;
            
            const label = document.createElement('span');
            label.textContent = series.label;
            
            legendItem.appendChild(colorBox);
            legendItem.appendChild(label);
            legendContainer.appendChild(legendItem);
        });
        
        // Create canvas wrapper
        const canvasWrapper = document.createElement('div');
        canvasWrapper.style.flex = '1';
        canvasWrapper.style.position = 'relative';
        canvasWrapper.appendChild(canvas);
        
        chartContainer.appendChild(canvasWrapper);
        chartContainer.appendChild(legendContainer);
        wrapper.appendChild(chartContainer);
        container.appendChild(wrapper);
        
        const ctx = canvas.getContext('2d');
        
        // Update canvas size based on actual container size
        const updateCanvasSize = () => {
            const containerRect = canvasWrapper.getBoundingClientRect();
            canvas.width = containerRect.width;
            canvas.height = containerRect.height;
        };
        updateCanvasSize();
        
        const width = canvas.width;
        const height = canvas.height;
        const padding = { top: 30, right: 20, bottom: 50, left: 70 };
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;
        
        // Reverse data arrays to show oldest to newest (left to right)
        const reversedData = data.map(series => ({
            ...series,
            values: [...series.values].reverse()
        }));
        const reversedLabels = [...labels].reverse();
        
        // Find min/max values
        let minVal = Infinity;
        let maxVal = -Infinity;
        reversedData.forEach(series => {
            series.values.forEach(val => {
                if (val !== null && val !== undefined && !isNaN(val)) {
                    minVal = Math.min(minVal, val);
                    maxVal = Math.max(maxVal, val);
                }
            });
        });
        
        if (minVal === Infinity) return;
        
        const range = maxVal - minVal || 1;
        const numPoints = reversedData[0].values.length;
        const stepX = chartWidth / (numPoints - 1 || 1);
        
        // Draw axes
        ctx.strokeStyle = '#dee2e6';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(padding.left, padding.top);
        ctx.lineTo(padding.left, padding.top + chartHeight);
        ctx.lineTo(padding.left + chartWidth, padding.top + chartHeight);
        ctx.stroke();
        
        // Draw zero line if needed
        if (minVal < 0 && maxVal > 0) {
            const zeroY = padding.top + chartHeight - ((0 - minVal) / range) * chartHeight;
            ctx.strokeStyle = '#999';
            ctx.lineWidth = 1;
            ctx.setLineDash([2, 2]);
            ctx.beginPath();
            ctx.moveTo(padding.left, zeroY);
            ctx.lineTo(padding.left + chartWidth, zeroY);
            ctx.stroke();
            ctx.setLineDash([]);
        }
        
        // Draw grid lines and Y-axis labels
        ctx.font = '10px Raleway';
        ctx.fillStyle = '#666';
        const numTicks = 5;
        for (let i = 0; i <= numTicks; i++) {
            const y = padding.top + chartHeight - (i / numTicks) * chartHeight;
            const value = minVal + (maxVal - minVal) * (i / numTicks);
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(padding.left + chartWidth, y);
            ctx.strokeStyle = '#e9ecef';
            ctx.stroke();
            ctx.fillText(formatFinancialValueForChart(value), 5, y + 4);
        }
        
        // Store data points for hover interaction (grouped by time index)
        const timePoints = [];
        for (let i = 0; i < numPoints; i++) {
            const x = padding.left + i * stepX;
            const pointData = {
                index: i,
                date: reversedLabels[i] || '',
                x: x,
                values: []
            };
            
            reversedData.forEach((series, seriesIdx) => {
                const val = series.values[i];
                if (val !== null && val !== undefined && !isNaN(val)) {
                    const y = padding.top + chartHeight - ((val - minVal) / range) * chartHeight;
                    pointData.values.push({
                        series: series.label,
                        value: val,
                        y: y,
                        color: colors[seriesIdx] || '#4dabf7'
                    });
                }
            });
            
            if (pointData.values.length > 0) {
                timePoints.push(pointData);
            }
        }
        
        // Draw data lines
        reversedData.forEach((series, seriesIdx) => {
            const color = colors[seriesIdx] || '#4dabf7';
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.beginPath();
            
            let firstPoint = true;
            series.values.forEach((val, i) => {
                if (val !== null && val !== undefined && !isNaN(val)) {
                    const x = padding.left + i * stepX;
                    const y = padding.top + chartHeight - ((val - minVal) / range) * chartHeight;
                    if (firstPoint) {
                        ctx.moveTo(x, y);
                        firstPoint = false;
                    } else {
                        ctx.lineTo(x, y);
                    }
                }
            });
            ctx.stroke();
            
            // Draw data points
            series.values.forEach((val, i) => {
                if (val !== null && val !== undefined && !isNaN(val)) {
                    const x = padding.left + i * stepX;
                    const y = padding.top + chartHeight - ((val - minVal) / range) * chartHeight;
                    ctx.fillStyle = color;
                    ctx.beginPath();
                    ctx.arc(x, y, 3, 0, 2 * Math.PI);
                    ctx.fill();
                }
            });
        });
        
        // Draw X-axis labels
        const labelStep = Math.max(1, Math.floor(numPoints / 6));
        reversedLabels.forEach((label, i) => {
            if (i % labelStep === 0 || i === reversedLabels.length - 1) {
                const x = padding.left + i * stepX;
                ctx.fillStyle = '#666';
                ctx.font = '9px Raleway';
                ctx.textAlign = 'center';
                ctx.save();
                ctx.translate(x, padding.top + chartHeight + 20);
                ctx.rotate(-Math.PI / 4);
                ctx.fillText(label, 0, 0);
                ctx.restore();
                ctx.textAlign = 'left';
            }
        });
        
        // Store original drawing function for redraw
        const redrawChart = (highlightedIndex = null) => {
            // Update canvas size in case of resize
            updateCanvasSize();
            const currentWidth = canvas.width;
            const currentHeight = canvas.height;
            
            // Clear canvas
            ctx.clearRect(0, 0, currentWidth, currentHeight);
            
            // Recalculate dimensions
            const currentChartWidth = currentWidth - padding.left - padding.right;
            const currentChartHeight = currentHeight - padding.top - padding.bottom;
            
            // Redraw axes
            ctx.strokeStyle = '#dee2e6';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(padding.left, padding.top);
            ctx.lineTo(padding.left, padding.top + currentChartHeight);
            ctx.lineTo(padding.left + currentChartWidth, padding.top + currentChartHeight);
            ctx.stroke();
            
            // Redraw zero line if needed
            if (minVal < 0 && maxVal > 0) {
                const zeroY = padding.top + currentChartHeight - ((0 - minVal) / range) * currentChartHeight;
                ctx.strokeStyle = '#999';
                ctx.lineWidth = 1;
                ctx.setLineDash([2, 2]);
                ctx.beginPath();
                ctx.moveTo(padding.left, zeroY);
                ctx.lineTo(padding.left + currentChartWidth, zeroY);
                ctx.stroke();
                ctx.setLineDash([]);
            }
            
            // Redraw grid lines and Y-axis labels
            ctx.font = '10px Raleway';
            ctx.fillStyle = '#666';
            for (let i = 0; i <= numTicks; i++) {
                const y = padding.top + currentChartHeight - (i / numTicks) * currentChartHeight;
                const value = minVal + (maxVal - minVal) * (i / numTicks);
                ctx.beginPath();
                ctx.moveTo(padding.left, y);
                ctx.lineTo(padding.left + currentChartWidth, y);
                ctx.strokeStyle = '#e9ecef';
                ctx.stroke();
                ctx.fillText(formatFinancialValueForChart(value), 5, y + 4);
            }
            
            // Recalculate stepX for current width
            const currentStepX = currentChartWidth / (numPoints - 1 || 1);
            
            // Draw data lines
            reversedData.forEach((series, seriesIdx) => {
                const color = colors[seriesIdx] || '#4dabf7';
                ctx.strokeStyle = color;
                ctx.lineWidth = 2;
                ctx.beginPath();
                
                let firstPoint = true;
                series.values.forEach((val, i) => {
                    if (val !== null && val !== undefined && !isNaN(val)) {
                        const x = padding.left + i * currentStepX;
                        const y = padding.top + currentChartHeight - ((val - minVal) / range) * currentChartHeight;
                        if (firstPoint) {
                            ctx.moveTo(x, y);
                            firstPoint = false;
                        } else {
                            ctx.lineTo(x, y);
                        }
                    }
                });
                ctx.stroke();
                
                // Draw data points
                series.values.forEach((val, i) => {
                    if (val !== null && val !== undefined && !isNaN(val)) {
                        const x = padding.left + i * currentStepX;
                        const y = padding.top + currentChartHeight - ((val - minVal) / range) * currentChartHeight;
                        const isHighlighted = highlightedIndex === i;
                        
                        // Draw point with highlight
                        ctx.fillStyle = color;
                        ctx.beginPath();
                        ctx.arc(x, y, isHighlighted ? 5 : 3, 0, 2 * Math.PI);
                        ctx.fill();
                        
                        // Draw highlight circle
                        if (isHighlighted) {
                            ctx.strokeStyle = color;
                            ctx.lineWidth = 2;
                            ctx.beginPath();
                            ctx.arc(x, y, 7, 0, 2 * Math.PI);
                            ctx.stroke();
                        }
                    }
                });
            });
            
            // Draw vertical line at highlighted point
            if (highlightedIndex !== null && highlightedIndex >= 0 && highlightedIndex < numPoints) {
                const x = padding.left + highlightedIndex * currentStepX;
                ctx.strokeStyle = '#666';
                ctx.lineWidth = 1;
                ctx.setLineDash([3, 3]);
                ctx.beginPath();
                ctx.moveTo(x, padding.top);
                ctx.lineTo(x, padding.top + currentChartHeight);
                ctx.stroke();
                ctx.setLineDash([]);
            }
            
            // Redraw X-axis labels
            const labelStep = Math.max(1, Math.floor(numPoints / 6));
            reversedLabels.forEach((label, i) => {
                if (i % labelStep === 0 || i === reversedLabels.length - 1) {
                    const x = padding.left + i * currentStepX;
                    ctx.fillStyle = '#666';
                    ctx.font = '9px Raleway';
                    ctx.textAlign = 'center';
                    ctx.save();
                    ctx.translate(x, padding.top + currentChartHeight + 20);
                    ctx.rotate(-Math.PI / 4);
                    ctx.fillText(label, 0, 0);
                    ctx.restore();
                    ctx.textAlign = 'left';
                }
            });
        };
        
        // Add hover interaction
        let hoveredIndex = null;
        let tooltip = null;
        
        const createTooltip = (pointData, mouseX, mouseY) => {
            if (tooltip) tooltip.remove();
            tooltip = document.createElement('div');
            tooltip.style.position = 'absolute';
            tooltip.style.backgroundColor = 'rgba(0, 0, 0, 0.85)';
            tooltip.style.color = 'white';
            tooltip.style.padding = '10px 14px';
            tooltip.style.borderRadius = '6px';
            tooltip.style.fontSize = '11px';
            tooltip.style.pointerEvents = 'none';
            tooltip.style.zIndex = '1000';
            tooltip.style.boxShadow = '0 2px 8px rgba(0,0,0,0.3)';
            
            // Build tooltip content with all data points
            let tooltipHTML = `<div style="font-weight: bold; margin-bottom: 6px; font-size: 12px;">${pointData.date}</div>`;
            pointData.values.forEach(valData => {
                tooltipHTML += `
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                        <div style="width: 12px; height: 12px; background-color: ${valData.color}; border-radius: 2px;"></div>
                        <div>${valData.series}: <strong>${formatFinancialValueForChart(valData.value)}</strong></div>
                    </div>
                `;
            });
            tooltip.innerHTML = tooltipHTML;
            wrapper.appendChild(tooltip);
            
            // Position tooltip
            const rect = wrapper.getBoundingClientRect();
            tooltip.style.left = `${mouseX + 15}px`;
            tooltip.style.top = `${mouseY - tooltip.offsetHeight / 2}px`;
            
            // Adjust if tooltip goes off screen
            const tooltipRect = tooltip.getBoundingClientRect();
            if (tooltipRect.right > window.innerWidth) {
                tooltip.style.left = `${mouseX - tooltipRect.width - 15}px`;
            }
            if (tooltipRect.top < 0) {
                tooltip.style.top = '10px';
            }
            if (tooltipRect.bottom > window.innerHeight) {
                tooltip.style.top = `${window.innerHeight - tooltipRect.height - 10}px`;
            }
            
            return tooltip;
        };
        
        canvas.addEventListener('mousemove', (e) => {
            const rect = canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            // Find closest time point (within reasonable distance)
            let closestPoint = null;
            let minDist = Infinity;
            const snapDistance = stepX * 0.5; // Snap to point if within half the step distance
            
            timePoints.forEach(point => {
                const dist = Math.abs(mouseX - point.x);
                if (dist < snapDistance && dist < minDist) {
                    minDist = dist;
                    closestPoint = point;
                }
            });
            
            if (closestPoint && (!hoveredIndex || hoveredIndex !== closestPoint.index)) {
                hoveredIndex = closestPoint.index;
                redrawChart(hoveredIndex);
                createTooltip(closestPoint, mouseX, mouseY);
            } else if (!closestPoint && hoveredIndex !== null) {
                hoveredIndex = null;
                redrawChart(null);
                if (tooltip) {
                    tooltip.remove();
                    tooltip = null;
                }
            } else if (closestPoint && hoveredIndex === closestPoint.index) {
                // Update tooltip position while hovering same point
                if (tooltip) {
                    const rect = wrapper.getBoundingClientRect();
                    tooltip.style.left = `${mouseX + 15}px`;
                    tooltip.style.top = `${mouseY - tooltip.offsetHeight / 2}px`;
                }
            }
        });
        
        canvas.addEventListener('mouseleave', () => {
            hoveredIndex = null;
            if (tooltip) {
                tooltip.remove();
                tooltip = null;
            }
            redrawChart(null);
        });
    };
    
    // Helper function to get value with field name mapping
    const getFieldValueForChart = (record, fieldName, camelCaseName) => {
        if (record[fieldName] !== undefined && record[fieldName] !== null) return record[fieldName];
        if (record[camelCaseName] !== undefined && record[camelCaseName] !== null) return record[camelCaseName];
        return null;
    };
    
    // Prepare Profitability Trend data
    if (incomeData.length > 0) {
        const dates = incomeData.map(d => {
            const date = d.fiscalDateEnding;
            if (!date) return '';
            // Handle both string and date object formats
            const dateStr = typeof date === 'string' ? date : date.toString();
            return dateStr.substring(0, 7);
        });
        const revenue = incomeData.map(d => {
            const val = getFieldValueForChart(d, 'Total Revenue', 'totalRevenue');
            return parseFloat(val) || 0;
        });
        const netIncome = incomeData.map(d => {
            const val = getFieldValueForChart(d, 'Net Income', 'netIncome');
            return parseFloat(val) || 0;
        });
        const grossProfit = incomeData.map(d => {
            const val = getFieldValueForChart(d, 'Gross Profit', 'grossProfit');
            return parseFloat(val) || 0;
        });
        
        renderTrendChart('profitability-trend-chart', [
            { values: revenue, label: 'Revenue' },
            { values: netIncome, label: 'Net Income' },
            { values: grossProfit, label: 'Gross Profit' }
        ], dates, 'Profitability', ['#4dabf7', '#26a69a', '#ff9800']);
    }
    
    // Prepare Debt-Asset Trend data
    if (balanceData.length > 0) {
        const dates = balanceData.map(d => {
            const date = d.fiscalDateEnding;
            if (!date) return '';
            const dateStr = typeof date === 'string' ? date : date.toString();
            return dateStr.substring(0, 7);
        });
        const totalAssets = balanceData.map(d => {
            const val = getFieldValueForChart(d, 'Total Assets', 'totalAssets');
            return parseFloat(val) || 0;
        });
        const totalLiab = balanceData.map(d => {
            const val = getFieldValueForChart(d, 'Total Liab', 'totalLiabilities') || getFieldValueForChart(d, 'Total Liabilities', 'totalLiabilities');
            return parseFloat(val) || 0;
        });
        const totalEquity = balanceData.map(d => {
            const val = getFieldValueForChart(d, 'Total Stockholder Equity', 'totalShareholderEquity');
            return parseFloat(val) || 0;
        });
        
        renderTrendChart('debt-asset-trend-chart', [
            { values: totalAssets, label: 'Total Assets' },
            { values: totalLiab, label: 'Total Liabilities' },
            { values: totalEquity, label: 'Total Equity' }
        ], dates, 'Debt-Asset', ['#4dabf7', '#ef5350', '#26a69a']);
    }
    
    // Prepare Cash Flow Trend data
    if (cashFlowData.length > 0) {
        const dates = cashFlowData.map(d => {
            const date = d.fiscalDateEnding;
            if (!date) return '';
            const dateStr = typeof date === 'string' ? date : date.toString();
            return dateStr.substring(0, 7);
        });
        const operatingCF = cashFlowData.map(d => {
            const val = getFieldValueForChart(d, 'Total Cash From Operating Activities', 'operatingCashflow');
            return parseFloat(val) || 0;
        });
        const freeCF = cashFlowData.map(d => {
            const val = getFieldValueForChart(d, 'Free Cash Flow', 'freeCashFlow');
            // Calculate if not available: Operating CF + Capital Expenditures
            if (val === null) {
                const opCF = getFieldValueForChart(d, 'Total Cash From Operating Activities', 'operatingCashflow');
                const capEx = getFieldValueForChart(d, 'Capital Expenditures', 'capitalExpenditures');
                return (parseFloat(opCF) || 0) + (parseFloat(capEx) || 0);
            }
            return parseFloat(val) || 0;
        });
        const investingCF = cashFlowData.map(d => {
            const val = getFieldValueForChart(d, 'Total Cashflows From Investing Activities', 'cashflowFromInvestment');
            return parseFloat(val) || 0;
        });
        
        renderTrendChart('cash-flow-trend-chart', [
            { values: operatingCF, label: 'Operating CF' },
            { values: freeCF, label: 'Free CF' },
            { values: investingCF, label: 'Investing CF' }
        ], dates, 'Cash Flow', ['#4dabf7', '#26a69a', '#ff9800']);
    }
}, [processedFundamentalData]);

    // Helper to align chart widths
    const alignChartWidths = () => {
        if (!priceChart.current || !volumeChart.current || !priceChartRef.current || !volumeChartRef.current) return;
        
        setTimeout(() => {
            try {
                // Sync visible time range
                const priceTimeScale = priceChart.current.timeScale();
                const priceRange = priceTimeScale.getVisibleRange();
                if (priceRange) {
                    volumeChart.current.timeScale().setVisibleRange(priceRange);
                }
                
                // Get the actual canvas widths and adjust volume chart to match price chart
                const priceCanvas = priceChartRef.current?.querySelector('canvas');
                const volumeCanvas = volumeChartRef.current?.querySelector('canvas');
                
                if (priceCanvas && volumeCanvas) {
                    const priceRect = priceCanvas.getBoundingClientRect();
                    const volumeRect = volumeCanvas.getBoundingClientRect();
                    const widthDiff = priceRect.width - volumeRect.width;
                    
                    // Adjust volume chart width if there's a difference
                    if (Math.abs(widthDiff) > 0) {
                        const currentVolWidth = volumeChart.current.options().width;
                        volumeChart.current.applyOptions({ width: currentVolWidth + widthDiff });
                    }
                }
            } catch (e) {
                // Silently handle sync errors
            }
        }, 100);
    };

    const updateCharts = () => {
        if (!stockData) return;

        try {
            // update price chart
            updatePriceChart();
            
            // update volume chart
            updateVolumeChart();
            
            // update technical indicators chart
            updateTechnicalChart();

            // re-bind events (important!)
            setTimeout(() => {
                if (priceChart.current) {
                    // Crosshair move event already handled in chart initialization
                    
                }
                // Ensure chart alignment after all updates
                alignChartWidths();
            }, 100);

        } catch (error) {
            console.error('Error updating charts:', error);
            setError('Failed to update charts: ' + error.message);
        }
    };

    const updatePriceChart = () => {
        if (!priceChart.current || !stockData.candlestick_data) return;

        try {
            // Clear existing MA series
            Object.values(maSeries.current).forEach(series => {
                if (series && priceChart.current) {
                    try {
                        priceChart.current.removeSeries(series);
                    } catch (error) {
                        // Silently handle removal errors
                    }
                }
            });
            maSeries.current = {};

            // Update candlestick data
            if (candlestickSeries.current) {
                candlestickSeries.current.setData(stockData.candlestick_data);
                priceChart.current.timeScale().fitContent();
            } else {
                // Recreate candlestick series if it doesn't exist
                candlestickSeries.current = priceChart.current.addCandlestickSeries({
                    upColor: '#26a69a',
                    downColor: '#ef5350',
                    borderVisible: false,
                    wickUpColor: '#26a69a',
                    wickDownColor: '#ef5350',
                    priceFormat: {
                        type: 'price',
                        precision: 2,
                        minMove: 0.01,
                    },
                    priceLineVisible: false,
                    lastValueVisible: false,
                });
                candlestickSeries.current.setData(stockData.candlestick_data);
                priceChart.current.timeScale().fitContent();
            }

            // 3. re-add moving averages - ONLY for the selected type
            if (stockData.ma_data && chartConfig.ma_options) {
                const colors = ['#A83838', '#F09A16', '#EFF048', '#5DF016', '#13C3F0', '#493CF0', '#F000DF'];
                let colorIndex = 0;

                // Only add the selected MA type
                const selectedMAType = chartConfig.ma_options.toLowerCase();
                if (stockData.ma_data[selectedMAType]) {
                    const dataArray = stockData.ma_data[selectedMAType];
                    
                    // Group data by period
                    const dataByPeriod = {};
                    dataArray.forEach(item => {
                        const period = item.period;
                        if (!dataByPeriod[period]) {
                            dataByPeriod[period] = [];
                        }
                        dataByPeriod[period].push({
                            time: item.time,
                            value: item.value
                        });
                    });

                    // Create series for each period
                    Object.entries(dataByPeriod).forEach(([period, data]) => {
                        const seriesName = `${selectedMAType.toUpperCase()}${period}`;
                        const isHighlighted = highlightedMA === seriesName;
                        
                            const series = priceChart.current.addLineSeries({
                                color: colors[colorIndex % colors.length],
                            lineWidth: isHighlighted ? 3 : 1,
                            visible: true,
                            lastValueVisible: false,
                            priceLineVisible: false,
                            });
                            series.setData(data);
                        maSeries.current[seriesName] = series;
                            colorIndex++;
                    });
                }

                // Add Bollinger Bands if they exist
                if (stockData.ma_data.bbands_upper && stockData.ma_data.bbands_lower) {
                    const color = '#ADD8E6';
                    
                    const upperSeries = priceChart.current.addLineSeries({
                                color: color,
                                lineWidth: 1,
                        lineStyle: 3, // dashed line style
                        visible: true,
                        lastValueVisible: false,
                        priceLineVisible: false,
                    });
                    upperSeries.setData(stockData.ma_data.bbands_upper);
                    maSeries.current['BBANDS_UPPER'] = upperSeries;

                    const lowerSeries = priceChart.current.addLineSeries({
                        color: color,
                        lineWidth: 1,
                        lineStyle: 3, // dashed line style
                        visible: true,
                        lastValueVisible: false,
                        priceLineVisible: false,
                    });
                    lowerSeries.setData(stockData.ma_data.bbands_lower);
                    maSeries.current['BBANDS_LOWER'] = lowerSeries;
                }
            }
        } catch (error) {
            console.error('Error updating price chart:', error);
        }
    };

    const updateVolumeChart = () => {
        if (!volumeChart.current || !stockData.volume_data) return;

        try {
            const volumeData = stockData.volume_data.map(item => ({
                time: item.time,
                value: item.value,
                color: item.color === 'green' ? 'rgba(0, 150, 136, 0.8)' : item.color === 'red' ? 'rgba(255,82,82, 0.8)' : 'rgba(117,117,117, 0.8)'
            }));

            if (volumeSeries.current) {
                volumeSeries.current.setData(volumeData);
            }
            
            // Force sync width and rightPriceScale with price chart after data is loaded
            alignChartWidths();
        } catch (error) {
            console.error('Error updating volume chart:', error);
        }
    };

    const updateTechnicalChart = () => {
        if (!technicalChart.current || !stockData.technical_data) return;

        try {
            // method A: clean up stored series references
            Object.values(technicalSeries.current).forEach(series => {
                if (series && technicalChart.current) {
                    try {
                        technicalChart.current.removeSeries(series);
                    } catch (error) {
                        console.warn('Error removing technical series:', error);
                    }
                }
            });
            technicalSeries.current = {};

            // method B: more thorough cleanup - remove all series from the chart
            // const allSeries = technicalChart.current.series();
            // allSeries.forEach(series => {
            //     try {
            //         technicalChart.current.removeSeries(series);
            //     } catch (error) {
            //         console.warn('Error removing series:', error);
            //     }
            // });

            const { technical_data } = stockData;

            // Only add the selected technical indicator
            if (chartConfig.tech_ind === 'macd') {
                // MACD line
                if (technical_data.macd_line) {
                    const macdSeries = technicalChart.current.addLineSeries({
                        color: 'orange',
                        lineWidth: 2,
                        //title: 'MACD',
                        visible: true,
                        lastValueVisible: false,
                        priceLineVisible: false,
                    });
                    macdSeries.setData(technical_data.macd_line);
                    technicalSeries.current.macd = macdSeries;
                }

                // signal line
                if (technical_data.signal_line) {
                    const signalSeries = technicalChart.current.addLineSeries({
                        color: 'deepskyblue',
                        lineWidth: 2,
                        //title: 'Signal',
                        visible: true,
                        lastValueVisible: false,
                        priceLineVisible: false,
                    });
                    signalSeries.setData(technical_data.signal_line);
                    technicalSeries.current.signal = signalSeries;
                }

                // MACD histogram
                if (technical_data.histogram) {
                    const histogramSeries = technicalChart.current.addHistogramSeries({
                        //title: 'MACD Histogram',
                        visible: true,
                        lastValueVisible: false,
                        priceLineVisible: false,
                    });
                    const histogramData = technical_data.histogram.map(item => ({
                        time: item.time,
                        value: item.value,
                        color: item.color === 'green' ? '#26a69a' : item.color === 'red' ? '#ef5350' : '#757575'
                    }));
                    histogramSeries.setData(histogramData);
                    technicalSeries.current.histogram = histogramSeries;
                }

            } else if (chartConfig.tech_ind === 'rsi') {
                if (technical_data.rsi_line) {
                    const rsiSeries = technicalChart.current.addLineSeries({
                        color: 'orange',
                        lineWidth: 2,
                        //title: 'RSI',
                        visible: true,
                        lastValueVisible: false,
                        priceLineVisible: false,
                    });
                    rsiSeries.setData(technical_data.rsi_line);
                    technicalSeries.current.rsi = rsiSeries;

                    // RSI overbought and oversold lines
                    const overboughtLine = technicalChart.current.addLineSeries({
                        color: 'red',
                        lineWidth: 1,
                        lineStyle: 2,
                        title: 'Overbought (80)',
                        visible: true,
                        lastValueVisible: false,
                        priceLineVisible: false,
                    });
                    overboughtLine.setData(technical_data.rsi_line.map(item => ({ time: item.time, value: 80 })));

                    const oversoldLine = technicalChart.current.addLineSeries({
                        color: 'green',
                        lineWidth: 1,
                        lineStyle: 2,
                        title: 'Oversold (20)',
                        visible: true,
                        lastValueVisible: false,
                        priceLineVisible: false,
                    });
                    oversoldLine.setData(technical_data.rsi_line.map(item => ({ time: item.time, value: 20 })));
                    
                    // ✅ critical fix: store these series references for next cleanup
                    technicalSeries.current.rsi_overbought = overboughtLine;
                    technicalSeries.current.rsi_oversold = oversoldLine;
                }

            } else if (chartConfig.tech_ind === 'kdj') {
                ['k_line', 'd_line', 'j_line'].forEach(line => {
                    if (technical_data[line]) {
                        const colorMap = { k_line: 'gold', d_line: 'blue', j_line: 'purple' };
                        const series = technicalChart.current.addLineSeries({
                            color: colorMap[line],
                            lineWidth: 2,
                            //title: line.toUpperCase().replace('_LINE', ''),
                            visible: true,
                            lastValueVisible: false,
                            priceLineVisible: false,
                        });
                        series.setData(technical_data[line]);
                        technicalSeries.current[line] = series;
                    }
                });
            }
        } catch (error) {
            console.error('Error updating technical chart:', error);
        }
    };

    const handleSearchParamChange = (key, value) => {
        if (key === 'ticker') {
            // Filter stocks as user types
            filterStocks(value);
        }
        
        setSearchParams(prev => ({
            ...prev,
            [key]: value
        }));
    };

    // Handle stock selection from suggestions
    const handleStockSelect = (stock) => {
        setSearchParams(prev => ({
            ...prev,
            ticker: stock.symbol
        }));
        setShowStockSuggestions(false);
        setFilteredStocks([]);
    };
    
    // Handle time range selection
    const handleTimeRangeClick = (timeRange) => {
        if (!priceChart.current) return;
        
        try {
            const timeScale = priceChart.current.timeScale();
            
            if (timeRange.step === 'all') {
                // Show all data
                timeScale.fitContent();
            } else {
                // Calculate the time range based on the step and count
                const now = Math.floor(Date.now() / 1000); // Current timestamp in seconds
                let fromTimestamp = now;
                
                const step = timeRange.step;
                const count = timeRange.count || 1;
                
                // Calculate time offset in seconds
                if (step === 'minute') {
                    fromTimestamp = now - (count * 60);
                } else if (step === 'hour') {
                    fromTimestamp = now - (count * 3600);
                } else if (step === 'day') {
                    fromTimestamp = now - (count * 86400);
                } else if (step === 'month') {
                    fromTimestamp = now - (count * 30 * 86400);
                } else if (step === 'year') {
                    fromTimestamp = now - (count * 365 * 86400);
                }
                
                // Set visible range
                timeScale.setVisibleRange({
                    from: fromTimestamp,
                    to: now
                });
            }
            
            // Align charts after time range change as Y-axis width might change
            alignChartWidths();
        } catch (error) {
            console.error('Error setting time range:', error);
        }
    };

    // Add a unified data update function
    const updateAllChartsData = (time, sourceIndex, sourceSeriesData) => {
        // Performance optimization: use indexed lookup instead of array searching
        
        const newCrosshairData = {
            price: null,
            volume: null,
            technical: null
        };

        // Get pre-indexed data for this time point (O(1) lookup)
        const timeData = indexedStockData ? indexedStockData.get(time) : null;
        
        if (!timeData && !sourceSeriesData) return;
        
        // 1. Process Price Chart data
        if (stockData && stockData.ma_data) {
            const priceInfo = {
                time: time,
                candlestick: null,
                ma_values: {}
            };
            
            // Get candlestick data - prefer indexed data (source of truth), fallback to sourceSeriesData
            if (timeData && timeData.candlestick) {
                priceInfo.candlestick = timeData.candlestick;
            } else if (sourceIndex === 0 && candlestickSeries.current && sourceSeriesData.has(candlestickSeries.current)) {
                priceInfo.candlestick = sourceSeriesData.get(candlestickSeries.current);
            }
            
            // Get moving average data
            if (timeData && timeData.ma) {
                // Use indexed data for all MAs at this time point
                priceInfo.ma_values = timeData.ma;
            } else if (sourceIndex === 0 && maSeries.current) {
                // Fallback to series data
                Object.entries(maSeries.current).forEach(([name, series]) => {
                    if (series && sourceSeriesData.has(series)) {
                        priceInfo.ma_values[name] = sourceSeriesData.get(series);
                    }
                });
            }
            
            newCrosshairData.price = priceInfo;
        }
        
        // 2. Process Volume Chart data
        if (stockData && stockData.volume_data) {
            let volumeData = null;
            
            // Get volume from indexed data
            if (timeData && timeData.volume) {
                volumeData = timeData.volume;
            } else if (sourceIndex === 1 && volumeSeries.current && sourceSeriesData.has(volumeSeries.current)) {
                // Fallback to series data, but try to recover color info
                const seriesData = sourceSeriesData.get(volumeSeries.current);
                volumeData = {
                    time: seriesData.time,
                    value: seriesData.value,
                    // Note: Series data might lose original color if not stored, defaulting to grey if full data missing
                    color: seriesData.color || 'rgba(117,117,117, 0.8)' 
                };
            }
            
            if (volumeData) {
                newCrosshairData.volume = {
                    time: time,
                    volume: volumeData
                };
            }
        }
        
        // 3. Process Technical Chart data
        if (stockData && stockData.technical_data) {
            const technicalValues = {};
            
            if (timeData && timeData.technical) {
                // Use indexed data
                Object.assign(technicalValues, timeData.technical);
            } else if (sourceIndex === 2 && technicalSeries.current) {
                // Fallback to series data
                const technicalKeyMapping = {
                    'macd': 'macd_line',
                    'signal': 'signal_line', 
                    'histogram': 'histogram',
                    'rsi': 'rsi_line',
                    'overbought': 'overbought_line',
                    'oversold': 'oversold_line',
                    'k': 'k_line',
                    'd': 'd_line',
                    'j': 'j_line'
                };
                
                Object.entries(technicalSeries.current).forEach(([seriesKey, series]) => {
                    if (series && sourceSeriesData.has(series)) {
                        const dataKey = technicalKeyMapping[seriesKey] || seriesKey;
                        technicalValues[dataKey] = sourceSeriesData.get(series);
                    }
                });
            }
            
            if (Object.keys(technicalValues).length > 0) {
                newCrosshairData.technical = {
                    time: time,
                    technical_values: technicalValues
                };
            }
        }
        
        setCrosshairData(newCrosshairData);
    };

    // Add helper function to find data at a specified time (Legacy/Backup)
    const findDataAtTime = (dataArray, targetTime) => {
        if (!dataArray || !Array.isArray(dataArray)) return null;
        
        // Find the data point closest to the target time
        return dataArray.find(item => item.time === targetTime) || null;
    };

    // Helper function to format financial values
    const formatFinancialValue = (value) => {
        if (value === null || value === undefined || value === '' || value === 'None') return 'N/A';
        const numValue = typeof value === 'string' ? parseFloat(value) : value;
        if (isNaN(numValue)) return 'N/A';
        if (Math.abs(numValue) >= 1e9) return `$${(numValue / 1e9).toFixed(2)}B`;
        if (Math.abs(numValue) >= 1e6) return `$${(numValue / 1e6).toFixed(2)}M`;
        if (Math.abs(numValue) >= 1e3) return `$${(numValue / 1e3).toFixed(2)}K`;
        return `$${numValue.toFixed(2)}`;
    };

    return (
        <div className="dashboard-container">
            {/* Slim Header */}
            <header className="app-header">
                <div className="header-left">
                    <div className="app-logo">Stock Matrix</div>
                    <div className="header-search">
                        <div className="stock-search-container">
                            <input
                                type="text"
                                value={searchParams.ticker}
                                onChange={(e) => handleSearchParamChange('ticker', e.target.value.toUpperCase())}
                                onFocus={() => {
                                    if (searchParams.ticker.length > 0) {
                                        filterStocks(searchParams.ticker);
                                    }
                                }}
                                onBlur={() => {
                                    setTimeout(() => setShowStockSuggestions(false), 200);
                                }}
                                placeholder="Search ticker..."
                            />
                            {showStockSuggestions && filteredStocks.length > 0 && (
                                <div className="stock-suggestions">
                                    {filteredStocks.map((stock, index) => (
                                        <div
                                            key={index}
                                            className="stock-suggestion-item"
                                            onClick={() => handleStockSelect(stock)}
                                        >
                                            <span className="stock-symbol">{stock.symbol}</span>
                                            <span className="stock-name">{stock.name}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                        <button 
                            onClick={() => fetchStockData()} 
                            disabled={loading}
                            className="fetch-button"
                        >
                            {loading ? 'Loading...' : 'Get Data'}
                        </button>
                    </div>
                </div>
            </header>

            {/* Error Info */}
            {error && (
                <div className="error-message">
                    Error: {error}
                </div>
            )}

            {/* Main Content: Two Column Layout */}
            <div className="main-content">
                {/* Left Column: Monitoring List */}
                <div className="info-column">
                    <div className="chart-section">
                        <div className="chart-title">
                            <span>Monitoring List</span>
                        </div>
                        <div style={{ padding: '20px', minHeight: '200px' }}>
                            {/* Content will be added later */}
                        </div>
                    </div>
                </div>

                {/* Right Column: Charts */}
                <div className="charts-column">
                    <div className="charts-wrapper">
                        {/* Company Overview Card - moved to top */}
                        <div className="chart-section">
                            <div className="chart-title">
                                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                                    <span>{stockData?.company_info?.longName || chartConfig.ticker}</span>
                                    <div className="ticker-badge">{chartConfig.ticker}</div>
                                    {stockData?.company_info?.exchange && (
                                        <span className="exchange-badge">{stockData.company_info.exchange}</span>
                                    )}
                                </div>
                            </div>
                            <div className="company-info-compact" style={{ position: 'relative' }}>
                                {loading && (
                                    <div className="chart-loading-overlay">
                                        <div className="loading-spinner"></div>
                                        Loading...
                                    </div>
                                )}
                                {stockData?.company_info && (
                                    <>
                                    <div className="metrics-compact">
                                        <div className="metric-group">
                                            <div className="metric-group-title">Overview</div>
                                            <div className="metric-row"><span>Sector</span><span>{stockData.company_info.sector || 'N/A'}</span></div>
                                            <div className="metric-row"><span>Industry</span><span>{stockData.company_info.industry || 'N/A'}</span></div>
                                        </div>

                                        <div className="metric-group">
                                            <div className="metric-group-title">Valuation</div>
                                            <div className="metric-row"><span>Mkt Cap</span><span>{stockData.company_info.marketCap ? `$${(stockData.company_info.marketCap / 1e9).toFixed(2)}B` : 'N/A'}</span></div>
                                            <div className="metric-row"><span>P/E</span><span>{stockData.company_info.peRatio != null ? stockData.company_info.peRatio : 'N/A'}</span></div>
                                            <div className="metric-row"><span>Fwd P/E</span><span>{stockData.company_info.forwardPE != null ? stockData.company_info.forwardPE : 'N/A'}</span></div>
                                            <div className="metric-row"><span>PEG</span><span>{stockData.company_info.pegRatio != null ? stockData.company_info.pegRatio : 'N/A'}</span></div>
                                            <div className="metric-row"><span>Div Yld</span><span>{stockData.company_info.dividendYield != null ? `${(stockData.company_info.dividendYield * 100).toFixed(2)}%` : 'N/A'}</span></div>
                                        </div>

                                        <div className="metric-group">
                                            <div className="metric-group-title">Financials</div>
                                            <div className="metric-row"><span>Rev(TTM)</span><span>{stockData.company_info.revenueTTM ? `$${(stockData.company_info.revenueTTM / 1e9).toFixed(2)}B` : 'N/A'}</span></div>
                                            <div className="metric-row"><span>EPS</span><span>{stockData.company_info.dilutedEPSTTM != null ? stockData.company_info.dilutedEPSTTM : (stockData.company_info.eps != null ? stockData.company_info.eps : 'N/A')}</span></div>
                                            <div className="metric-row"><span>Profit Mgn</span><span>{stockData.company_info.profitMargin != null ? `${(stockData.company_info.profitMargin * 100).toFixed(2)}%` : 'N/A'}</span></div>
                                            <div className="metric-row"><span>ROE</span><span>{stockData.company_info.returnOnEquityTTM != null ? `${(stockData.company_info.returnOnEquityTTM * 100).toFixed(2)}%` : 'N/A'}</span></div>
                                        </div>

                                        <div className="metric-group">
                                            <div className="metric-group-title">Price Stats</div>
                                            <div className="metric-row"><span>Beta</span><span>{stockData.company_info.beta != null ? stockData.company_info.beta : 'N/A'}</span></div>
                                            <div className="metric-row"><span>52W High</span><span>{stockData.company_info['52WeekHigh'] != null ? stockData.company_info['52WeekHigh'] : 'N/A'}</span></div>
                                            <div className="metric-row"><span>52W Low</span><span>{stockData.company_info['52WeekLow'] != null ? stockData.company_info['52WeekLow'] : 'N/A'}</span></div>
                                            <div className="metric-row"><span>Target</span><span>{stockData.company_info.analystTargetPrice != null ? stockData.company_info.analystTargetPrice : 'N/A'}</span></div>
                                        </div>

                                        <div className="metric-group metric-group-about">
                                            <div className="metric-group-title">About</div>
                                            <div className="about-text-box">
                                                {stockData.company_info.longBusinessSummary}
                                            </div>
                                        </div>
                                    </div>
                                    </>
                                )}
                            </div>
                        </div>

                {/* price chart */}
                <div className="chart-section">
                    <div className="chart-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                            <span>Stock Price & Moving Averages</span>
                            
                            {/* Interval Selector */}
                    <select
                                value={searchParams.interval}
                                onChange={(e) => handleImmediateChange('interval', e.target.value)}
                                style={{ 
                                    padding: '2px 5px', 
                                    borderRadius: '4px', 
                                    border: '1px solid #ccc',
                                    fontSize: '12px',
                                    backgroundColor: 'white'
                                }}
                            >
                                <option value="1m">1m</option>
                                <option value="5m">5m</option>
                                <option value="15m">15m</option>
                                <option value="30m">30m</option>
                                <option value="60m">1h</option>
                                <option value="1d">1D</option>
                                <option value="1wk">1W</option>
                                <option value="1mo">1M</option>
                    </select>

                            {/* MA Selector */}
                    <select
                                value={searchParams.ma_options}
                                onChange={(e) => handleImmediateChange('ma_options', e.target.value)}
                                style={{ 
                                    padding: '2px 5px', 
                                    borderRadius: '4px', 
                                    border: '1px solid #ccc',
                                    fontSize: '12px',
                                    backgroundColor: 'white'
                                }}
                            >
                                <option value="">No MA</option>
                        <option value="sma">SMA</option>
                        <option value="ema">EMA</option>
                        <option value="wma">WMA</option>
                        <option value="dema">DEMA</option>
                        <option value="tema">TEMA</option>
                        <option value="kama">KAMA</option>
                    </select>
                </div>

                        {/* TradingView Lightweight Charts Attribution */}
                        <div style={{ fontSize: '12px', color: '#666', marginLeft: 'auto', padding: '0 10px', lineHeight: '1.2', whiteSpace: 'nowrap' }}>
                            Charts powered by{' '}
                            <a 
                                href="https://www.tradingview.com/lightweight-charts/" 
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{ color: '#666', textDecoration: 'underline' }}
                            >
                                TradingView Lightweight Charts
                            </a>
                        </div>
                </div>

                    {/* Time Range Selector */}
                    {timeRanges.length > 0 && (
                        <div className="time-range-selector" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                {timeRanges.map((range, index) => (
                        <button 
                                        key={index}
                                        className="time-range-button"
                                        onClick={() => handleTimeRangeClick(range)}
                                    >
                                        {range.label}
                        </button>
                                ))}
                            </div>
                            
                            {chartConfig.interval === '1d' && (
                                <span style={{ fontSize: '11px', fontWeight: 'normal', color: '#666', marginLeft: 'auto', paddingRight: '16px' }}>
                                    📊 Daily prices are adjusted for dividends and stock splits
                                </span>
                            )}
            </div>
                    )}
                    
                    <div className="chart-container" style={{ marginBottom: 0, paddingBottom: 0, borderBottomLeftRadius: 0, borderBottomRightRadius: 0, borderBottom: 'none' }}>
                        {(loading || chartLoading || maLoading) && (
                            <div className="chart-loading-overlay">
                                <div className="loading-spinner"></div>
                                Loading...
                </div>
            )}
                        <div 
                            ref={priceChartRef} 
                            className="price-chart"
                        />
                        {stockData && stockData.ma_data && (
                            <div className="chart-legend">
                                {/* Render only the selected MA type */}
                                {(() => {
                                    const selectedMAType = chartConfig.ma_options?.toLowerCase();
                                    if (!selectedMAType || !stockData.ma_data[selectedMAType]) return null;
                                    
                                    const dataArray = stockData.ma_data[selectedMAType];
                                    const colors = ['#A83838', '#F09A16', '#EFF048', '#5DF016', '#13C3F0', '#493CF0', '#F000DF'];
                                    
                                    // Group data by period
                                    const dataByPeriod = {};
                                    dataArray.forEach(item => {
                                        const period = item.period;
                                        if (!dataByPeriod[period]) {
                                            dataByPeriod[period] = [];
                                        }
                                        dataByPeriod[period].push({
                                            time: item.time,
                                            value: item.value
                                        });
                                    });
                                    
                                    let colorIndex = 0;
                                    return Object.entries(dataByPeriod).map(([period, data]) => {
                                        const seriesName = `${selectedMAType.toUpperCase()}${period}`;
                                        const color = colors[colorIndex % colors.length];
                                        colorIndex++;
                                        
                                        let displayValue = 'N/A';
                                        if (crosshairData && crosshairData.price && crosshairData.price.ma_values[seriesName] && crosshairData.price.ma_values[seriesName].value !== undefined) {
                                            displayValue = crosshairData.price.ma_values[seriesName].value.toFixed(2);
                                        }
                                        
                                        // check if should be highlighted (only for MA lines)
                                        const isHighlighted = highlightedMA === seriesName;
                                        
                                        return (
                                            <div 
                                                key={seriesName} 
                                                className={`legend-item ${isHighlighted ? 'legend-item-highlighted' : ''}`}
                                                style={{
                                                    backgroundColor: isHighlighted ? 'rgba(255, 255, 0, 0.2)' : 'transparent',
                                                    border: isHighlighted ? '2px solid #FFD700' : '2px solid transparent',
                                                    borderRadius: '4px',
                                                    padding: '2px',
                                                    transition: 'all 0.2s ease'
                                                }}
                                            >
                                                <div 
                                                    className="legend-color" 
                                                    style={{ 
                                                        backgroundColor: color,
                                                        transform: isHighlighted ? 'scale(1.2)' : 'scale(1)',
                                                        transition: 'transform 0.2s ease'
                                                    }}
                                                ></div>
                                                <span 
                                                    className="legend-label"
                                                    style={{
                                                        fontWeight: 'bold',
                                                        color: isHighlighted ? 'black' : 'inherit'
                                                    }}
                                                >{seriesName}</span>
                                                <span 
                                                    className="legend-value"
                                                    style={{
                                                        fontWeight: 'bold',
                                                        color: isHighlighted ? 'black' : 'inherit'
                                                    }}
                                                >{displayValue}</span>
                </div>
                                        );
                                    });
                                })()}
                                
                                {/* Render Bollinger Bands if they exist */}
                                {stockData.ma_data.bbands_upper && stockData.ma_data.bbands_lower && (
                                    <>
                                        {['BBANDS_UPPER', 'BBANDS_LOWER'].map(name => {
                                            const color = '#ADD8E6';
                                            const displayName = name === 'BBANDS_UPPER' ? 'BB Upper' : 'BB Lower';
                                            
                                            let displayValue = 'N/A';
                                            if (crosshairData && crosshairData.price && crosshairData.price.ma_values[name] && crosshairData.price.ma_values[name].value !== undefined) {
                                                displayValue = crosshairData.price.ma_values[name].value.toFixed(2);
                                            }
                                            
                                            return (
                                                <div key={name} className="legend-item">
                                                    <div 
                                                        style={{ 
                                                            backgroundColor: 'transparent',
                                                            borderTop: `2px dashed ${color}`,
                                                            height: '0px',
                                                            width: '12px',
                                                            marginRight: '6px',
                                                            flexShrink: 0
                                                        }}
                                                    ></div>
                                                    <span className="legend-label">{displayName}</span>
                                                    <span className="legend-value">{displayValue}</span>
                                                </div>
                                            );
                                        })}
                                    </>
                                )}
                                
                                {/* display candlestick data */}
                                {crosshairData && crosshairData.price && crosshairData.price.candlestick && (
                                    <div className="legend-section">
                                        <div className="legend-title">
                                            Stock Price
                                            {chartConfig.interval === '1d' && (
                                                <span className="adjusted-label"> (Adj.)</span>
                                            )}
                                        </div>
                                        <div className="legend-item">
                                            <span className="legend-label">Open:</span>
                                            <span className="legend-value">{crosshairData.price.candlestick.open?.toFixed(2) || 'N/A'}</span>
                                        </div>
                                        <div className="legend-item">
                                            <span className="legend-label">High:</span>
                                            <span className="legend-value">{crosshairData.price.candlestick.high?.toFixed(2) || 'N/A'}</span>
                                        </div>
                                        <div className="legend-item">
                                            <span className="legend-label">Low:</span>
                                            <span className="legend-value">{crosshairData.price.candlestick.low?.toFixed(2) || 'N/A'}</span>
                                        </div>
                                        <div 
                                            className="legend-item"
                                            style={{
                                                border: `2px solid ${crosshairData.price.candlestick.close >= crosshairData.price.candlestick.open 
                                                    ? '#26a69a'  // green border
                                                    : '#ef5350'}`, // red border
                                                borderRadius: '4px',
                                                padding: '2px 4px',
                                                backgroundColor: 'rgba(255, 255, 255, 0.1)'
                                            }}
                                        >
                                            <span 
                                                className="legend-label"
                                                style={{
                                                    color: crosshairData.price.candlestick.close >= crosshairData.price.candlestick.open 
                                                        ? '#26a69a'  // green
                                                        : '#ef5350'  // red
                                                }}
                                            >
                                                Close:
                                            </span>
                                            <span 
                                                className="legend-value"
                                                style={{
                                                    fontWeight: 'bold',
                                                    color: crosshairData.price.candlestick.close >= crosshairData.price.candlestick.open 
                                                        ? '#26a69a'  // green
                                                        : '#ef5350'  // red
                                                }}
                                            >
                                                {crosshairData.price.candlestick.close?.toFixed(2) || 'N/A'}
                                            </span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                </div>

                    {/* Volume Chart - stacked below, sharing time axis */}
                    <div className="chart-container" style={{ marginTop: 0, paddingTop: 0, borderTop: '1px solid #d0d0d0', borderTopLeftRadius: 0, borderTopRightRadius: 0 }}>
                        {(loading || chartLoading) && (
                            <div className="chart-loading-overlay">
                                <div className="loading-spinner"></div>
                                Loading...
                            </div>
                        )}
                    <div 
                        ref={volumeChartRef} 
                            className="volume-chart"
                        />
                        
                        {/* Volume Legend - use the same response mechanism as price chart */}
                        {stockData && (
                            <div className="chart-legend">
                                {crosshairData && crosshairData.volume && crosshairData.volume.volume ? (
                                    <div className="legend-section">
                                        <div className="legend-item">
                                            {/* dynamic color and square shape of volume indicator */}
                                            {(() => {
                                                const volumeItem = crosshairData.volume.volume;
                                                // use same logic as chart
                                                const volumeColor = volumeItem.color === 'green' ? '#26a69a' : 
                                                                  volumeItem.color === 'red' ? '#ef5350' : '#757575';
                                                
                                                return (
                                                    <div 
                                                        className="legend-color volume-square" 
                                                        style={{ 
                                                            backgroundColor: volumeColor,
                                                            borderRadius: '0px', // square
                                                            width: '12px',
                                                            height: '12px'
                                                        }}
                                                    ></div>
                                                );
                                            })()}
                                            <span className="legend-label">Volume:</span>
                                            <span className="legend-value">
                                                {(crosshairData.volume.volume.value / 1000000).toFixed(2)}M
                                            </span>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="legend-section">
                                        <div className="legend-item">
                                            {/* default state of volume indicator - display N/A */}
                                            <div 
                                                className="legend-color volume-square" 
                                                style={{ 
                                                    backgroundColor: '#757575', // default gray
                                                    borderRadius: '0px', // square
                                                    width: '12px',
                                                    height: '12px'
                                                }}
                                            ></div>
                                            <span className="legend-label">Volume:</span>
                                            <span className="legend-value">N/A</span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>

                {/* technical indicators chart */}
                <div className="chart-section">
                    <div className="chart-title" style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                        <span>Technical Indicators - {chartConfig.tech_ind ? chartConfig.tech_ind.toUpperCase() : 'None'}</span>
                        <select
                            value={searchParams.tech_ind}
                            onChange={(e) => handleImmediateChange('tech_ind', e.target.value)}
                            style={{ 
                                padding: '2px 5px', 
                                borderRadius: '4px', 
                                border: '1px solid #ccc',
                                fontSize: '12px',
                                backgroundColor: 'white'
                            }}
                        >
                            <option value="">None</option>
                            <option value="macd">MACD</option>
                            <option value="rsi">RSI</option>
                            <option value="kdj">KDJ</option>
                        </select>
                    </div>
                    <div className="chart-container">
                        {(loading || techLoading) && (
                            <div className="chart-loading-overlay">
                                <div className="loading-spinner"></div>
                                Loading...
                            </div>
                        )}
                    <div 
                        ref={technicalChartRef} 
                            className="technical-chart"
                        />
                        
                        {/* Technical Legend - only show selected indicator */}
                        {stockData && stockData.technical_data && (
                            <div className="chart-legend">
                                {(() => {
                                    const selectedTechInd = chartConfig.tech_ind;
                                    const colors = {
                                        'macd_line': '#FF6B35',
                                        'signal_line': 'deepskyblue', 
                                        'histogram': '#1A936F',
                                        'rsi_line': '#FF6B35',
                                        'overbought_line': '#E74C3C',
                                        'oversold_line': '#E74C3C',
                                        'k_line': '#FFD700',
                                        'd_line': '#4169E1',
                                        'j_line': '#8A2BE2'
                                    };
                                    
                                    // Only show indicators for the selected technical indicator
                                    if (selectedTechInd === 'macd') {
                                        return ['macd_line', 'signal_line', 'histogram'].map(name => {
                                            if (!stockData.technical_data[name]) return null;
                                            
                                            const displayName = name === 'histogram' ? 'MACD Histogram' : 
                                                              name === 'macd_line' ? 'MACD' : 
                                                              name === 'signal_line' ? 'Signal' : name.replace('_', ' ').toUpperCase();
                                            
                                            let displayValue = 'N/A';
                                            let currentValue = null;
                                            
                                            if (crosshairData && crosshairData.technical && crosshairData.technical.technical_values && crosshairData.technical.technical_values[name]) {
                                                currentValue = crosshairData.technical.technical_values[name].value;
                                                displayValue = currentValue?.toFixed(2) || 'N/A';
                                            }
                                    
                                    // set dynamic color and square shape for MACD Histogram
                                    let legendColorStyle = {};
                                    let legendColorClass = 'legend-color';
                                    
                                    if (name === 'histogram') {
                                        // set color based on value positive or negative
                                        const histogramColor = currentValue >= 0 ? '#26a69a' : '#ef5350'; // green for positive, red for negative
                                        legendColorStyle = { 
                                            backgroundColor: histogramColor,
                                            borderRadius: '0px', // square
                                            width: '12px',
                                            height: '12px'
                                        };
                                        legendColorClass = 'legend-color histogram-square';
                                    } else {
                                        // other indicators use default color and circle
                                        legendColorStyle = { backgroundColor: colors[name] || '#666' };
                                    }
                                    
                                            return (
                                                <div key={name} className="legend-item">
                                                    <div className={legendColorClass} style={legendColorStyle}></div>
                                                    <span className="legend-label">{displayName}:</span>
                                                    <span className="legend-value">{displayValue}</span>
                </div>
                                            );
                                        }).filter(Boolean);
                                    } else if (selectedTechInd === 'rsi') {
                                        return ['rsi_line', 'overbought_line', 'oversold_line'].map(name => {
                                            if (!stockData.technical_data[name === 'rsi_line' ? 'rsi_line' : name]) return null;
                                            
                                            const displayName = name === 'rsi_line' ? 'RSI' : 
                                                              name === 'overbought_line' ? 'Overbought (80)' : 
                                                              name === 'oversold_line' ? 'Oversold (20)' : name.replace('_', ' ').toUpperCase();
                                            
                                            let displayValue = 'N/A';
                                            let currentValue = null;
                                            
                                            if (crosshairData && crosshairData.technical && crosshairData.technical.technical_values && crosshairData.technical.technical_values[name]) {
                                                currentValue = crosshairData.technical.technical_values[name].value;
                                                displayValue = currentValue?.toFixed(2) || 'N/A';
                                            }
                                            
                                            return (
                                                <div key={name} className="legend-item">
                                                    <div className="legend-color" style={{ backgroundColor: colors[name] || '#666' }}></div>
                                                    <span className="legend-label">{displayName}:</span>
                                                    <span className="legend-value">{displayValue}</span>
                                                </div>
                                            );
                                        }).filter(Boolean);
                                    } else if (selectedTechInd === 'kdj') {
                                        return ['k_line', 'd_line', 'j_line'].map(name => {
                                            if (!stockData.technical_data[name]) return null;
                                            
                                            const displayName = name.replace('_line', '').toUpperCase();
                                            
                                            let displayValue = 'N/A';
                                            let currentValue = null;
                                            
                                            if (crosshairData && crosshairData.technical && crosshairData.technical.technical_values && crosshairData.technical.technical_values[name]) {
                                                currentValue = crosshairData.technical.technical_values[name].value;
                                                displayValue = currentValue?.toFixed(2) || 'N/A';
                                            }
                                            
                                            return (
                                                <div key={name} className="legend-item">
                                                    <div className="legend-color" style={{ backgroundColor: colors[name] || '#666' }}></div>
                                                    <span className="legend-label">{displayName}:</span>
                                                    <span className="legend-value">{displayValue}</span>
                                                </div>
                                            );
                                        }).filter(Boolean);
                                    }
                                    
                                    return null;
                                })()}
                            </div>
                        )}
                    </div>
                </div>

                {/* Fundamental Data and News & Sentiment side by side */}
                <div style={{ display: 'flex', gap: '20px', alignItems: 'flex-start' }}>
                    {/* Fundamental Data Card - 2/3 width */}
                    <div className="chart-section" style={{ flex: '2', minWidth: 0 }}>
                        <div className="chart-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span>Fundamental Data</span>
                            <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
                                <label style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '5px', cursor: 'pointer' }}>
                                    <input
                                        type="radio"
                                        name="fundamentalPeriod"
                                        value="Quarterly"
                                        checked={fundamentalPeriod === 'Quarterly'}
                                        onChange={(e) => setFundamentalPeriod(e.target.value)}
                                        style={{ cursor: 'pointer' }}
                                    />
                                    Quarterly
                                </label>
                                <label style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '5px', cursor: 'pointer' }}>
                                    <input
                                        type="radio"
                                        name="fundamentalPeriod"
                                        value="Yearly"
                                        checked={fundamentalPeriod === 'Yearly'}
                                        onChange={(e) => setFundamentalPeriod(e.target.value)}
                                        style={{ cursor: 'pointer' }}
                                    />
                                    Yearly
                                </label>
                            </div>
                        </div>
                        
                        <div className="fundamental-data-container" style={{ position: 'relative' }}>
                        {fundamentalLoading && (
                            <div className="chart-loading-overlay">
                                <div className="loading-spinner"></div>
                                Loading...
                            </div>
                        )}
                        {!processedFundamentalData ? (
                            <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
                                {!stockData?.fundamental_data 
                                    ? 'No fundamental data available. Please search for a ticker to load data.'
                                    : `No fundamental data available for ${fundamentalPeriod} period`
                                }
                            </div>
                        ) : (
                            (() => {
                                const { incomeMapped, balanceMapped, cashFlowMapped, formattedReportDate } = processedFundamentalData;
                                
                                return (
                                <>
                                    {/* Most Recent Fundamental Metrics */}
                                    <div className="fundamental-section">
                                        <h4 className="section-title">Most Recent Fundamental Metrics</h4>
                                        <div className="fundamental-tables-grid">
                                            {/* Income Statement Table */}
                                            <div className="fundamental-table-container">
                                                <div className="table-title">Income Statement</div>
                                                <table className="fundamental-table">
                                                    <tbody>
                                                        <tr><td>Total Revenue</td><td>{formatFinancialValue(incomeMapped['Total Revenue'])}</td></tr>
                                                        <tr><td>Cost of Revenue</td><td>{formatFinancialValue(incomeMapped['Cost Of Revenue'])}</td></tr>
                                                        <tr><td>Gross Profit</td><td>{formatFinancialValue(incomeMapped['Gross Profit'])}</td></tr>
                                                        <tr><td>Operating Income</td><td>{formatFinancialValue(incomeMapped['Operating Income'])}</td></tr>
                                                        <tr><td>Net Income</td><td>{formatFinancialValue(incomeMapped['Net Income'])}</td></tr>
                                                        <tr><td>Net Profit Margin</td><td>{incomeMapped['Net Profit Margin'] != null ? `${(incomeMapped['Net Profit Margin'] * 100).toFixed(2)}%` : 'N/A'}</td></tr>
                                                    </tbody>
                                                </table>
                                            </div>
                                            
                                            {/* Balance Sheet Table */}
                                            <div className="fundamental-table-container">
                                                <div className="table-title">Balance Sheet</div>
                                                <table className="fundamental-table">
                                                    <tbody>
                                                        <tr><td>Total Assets</td><td>{formatFinancialValue(balanceMapped['Total Assets'])}</td></tr>
                                                        <tr><td>Total Liabilities</td><td>{formatFinancialValue(balanceMapped['Total Liab'])}</td></tr>
                                                        <tr><td>Total Equity</td><td>{formatFinancialValue(balanceMapped['Total Stockholder Equity'])}</td></tr>
                                                        <tr><td>Cash & Equivalents</td><td>{formatFinancialValue(balanceMapped['Cash'])}</td></tr>
                                                        <tr><td>Current Assets</td><td>{formatFinancialValue(balanceMapped['Total Current Assets'])}</td></tr>
                                                        <tr><td>Current Liabilities</td><td>{formatFinancialValue(balanceMapped['Total Current Liabilities'])}</td></tr>
                                                    </tbody>
                                                </table>
                                            </div>
                                            
                                            {/* Cash Flow Table */}
                                            <div className="fundamental-table-container">
                                                <div className="table-title">Cash Flow</div>
                                                <table className="fundamental-table">
                                                    <tbody>
                                                        <tr><td>Operating Cash Flow</td><td>{formatFinancialValue(cashFlowMapped['Total Cash From Operating Activities'])}</td></tr>
                                                        <tr><td>Investing Cash Flow</td><td>{formatFinancialValue(cashFlowMapped['Total Cashflows From Investing Activities'])}</td></tr>
                                                        <tr><td>Financing Cash Flow</td><td>{formatFinancialValue(cashFlowMapped['Total Cash From Financing Activities'])}</td></tr>
                                                        <tr><td>Capital Expenditure</td><td>{formatFinancialValue(cashFlowMapped['Capital Expenditures'])}</td></tr>
                                                        <tr><td>Free Cash Flow</td><td>{formatFinancialValue(cashFlowMapped['Free Cash Flow'])}</td></tr>
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                        <div className="report-date-footnote">
                                            Most recent report date: {formattedReportDate}
                                        </div>
                                    </div>
                                    
                                    {/* Profitability Trend */}
                                    <div className="fundamental-section">
                                        <h4 className="section-title">Profitability Trend</h4>
                                        <div className="trend-chart-container" id="profitability-trend-chart">
                                            {/* Chart will be rendered here */}
                                        </div>
                                    </div>
                                    
                                    {/* Debt-Asset Trend */}
                                    <div className="fundamental-section">
                                        <h4 className="section-title">Debt-Asset Trend</h4>
                                        <div className="trend-chart-container" id="debt-asset-trend-chart">
                                            {/* Chart will be rendered here */}
                                        </div>
                                    </div>
                                    
                                    {/* Cash Flow Trend */}
                                    <div className="fundamental-section">
                                        <h4 className="section-title">Cash Flow Trend</h4>
                                        <div className="trend-chart-container" id="cash-flow-trend-chart">
                                            {/* Chart will be rendered here */}
                                        </div>
                                    </div>
                                </>
                                );
                            })()
                        )}
                        </div>
                    </div>

                    {/* News & Sentiment Analysis card - 1/3 width */}
                    <div className="chart-section" style={{ flex: '1', minWidth: 0 }}>
                        <div className="chart-title">
                            <span>News & Sentiment Analysis</span>
                        </div>
                        <div className="news-sentiment-container" style={{ position: 'relative' }}>
                            {loading && (
                                <div className="chart-loading-overlay">
                                    <div className="loading-spinner"></div>
                                    Loading...
                                </div>
                            )}
                            {!stockData?.news_sentiment ? (
                                <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
                                    No news sentiment data available
                                </div>
                            ) : (() => {
                                const newsData = stockData.news_sentiment;
                                const avgScore = newsData.average_sentiment_score || 0;
                                const sentimentLabel = newsData.average_sentiment_label || 'Neutral';
                                const articles = newsData.articles || [];
                                
                                // Calculate gauge angle (score ranges from -1 to 1, gauge from 0 to 180 degrees)
                                // -1 maps to 0 degrees (left), 0 maps to 90 degrees (center), +1 maps to 180 degrees (right)
                                const gaugeAngle = ((avgScore + 1) / 2) * 180; // Convert -1 to 1 range to 0 to 180 degrees
                                
                                // Determine color based on sentiment
                                let gaugeColor = '#666'; // Neutral
                                if (avgScore >= 0.35) gaugeColor = '#26a69a'; // Bullish - green
                                else if (avgScore >= 0.15) gaugeColor = '#66bb6a'; // Somewhat Bullish - light green
                                else if (avgScore >= -0.15) gaugeColor = '#ffa726'; // Neutral - orange
                                else if (avgScore >= -0.35) gaugeColor = '#ef5350'; // Somewhat Bearish - light red
                                else gaugeColor = '#c62828'; // Bearish - dark red
                                
                                // Calculate arc end point
                                const centerX = 100;
                                const centerY = 100;
                                const radius = 80;
                                const startAngle = 0; // Start from left (0 degrees)
                                const endAngle = gaugeAngle; // End at calculated angle
                                
                                // Calculate arc path
                                const startX = centerX - radius;
                                const startY = centerY;
                                const endX = centerX - radius * Math.cos(endAngle * Math.PI / 180);
                                const endY = centerY - radius * Math.sin(endAngle * Math.PI / 180);
                                
                                // Large arc flag: 1 if angle > 180, 0 otherwise
                                const largeArcFlag = endAngle > 180 ? 1 : 0;
                                
                                return (
                                    <>
                                        {/* Gauge Visualization */}
                                        <div style={{ padding: '20px', display: 'flex', alignItems: 'center', gap: '20px' }}>
                                            <div style={{ position: 'relative', width: '200px', height: '120px', flexShrink: 0 }}>
                                                <svg width="200" height="120" viewBox="0 0 200 120" style={{ overflow: 'visible' }}>
                                                    {/* Background arc (full semicircle) */}
                                                    <path
                                                        d="M 20 100 A 80 80 0 0 1 180 100"
                                                        fill="none"
                                                        stroke="#e0e0e0"
                                                        strokeWidth="12"
                                                        strokeLinecap="round"
                                                    />
                                                    {/* Sentiment arc (colored portion) */}
                                                    {gaugeAngle > 0 && (
                                                        <path
                                                            d={`M ${startX} ${startY} A ${radius} ${radius} 0 ${largeArcFlag} 1 ${endX} ${endY}`}
                                                            fill="none"
                                                            stroke={gaugeColor}
                                                            strokeWidth="12"
                                                            strokeLinecap="round"
                                                            style={{ transition: 'all 0.5s ease' }}
                                                        />
                                                    )}
                                                    {/* Needle */}
                                                    <line
                                                        x1={centerX}
                                                        y1={centerY}
                                                        x2={endX}
                                                        y2={endY}
                                                        stroke="#333"
                                                        strokeWidth="3"
                                                        strokeLinecap="round"
                                                        style={{ transition: 'all 0.5s ease' }}
                                                    />
                                                    {/* Center dot */}
                                                    <circle cx={centerX} cy={centerY} r="5" fill="#333" />
                                                    {/* Labels - enlarged */}
                                                    <text x="20" y="110" fontSize="14" fill="#999" fontWeight="600">-1</text>
                                                    <text x="175" y="110" fontSize="14" fill="#999" fontWeight="600">+1</text>
                                                    {/* Average score below center point */}
                                                    <text x={centerX} y={centerY + 25} fontSize="20" fill={gaugeColor} fontWeight="bold" textAnchor="middle">
                                                        {avgScore.toFixed(3)}
                                                    </text>
                                                </svg>
                                            </div>
                                            {/* Text info on the right side */}
                                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '10px' }}>
                                                <div style={{ fontSize: '16px', fontWeight: '600', color: gaugeColor }}>
                                                    {sentimentLabel}
                                                </div>
                                                <div style={{ fontSize: '13px', color: '#666' }}>
                                                    {newsData.total_articles || 0} articles (24h)
                                                </div>
                                            </div>
                                        </div>
                                        
                                        {/* News List */}
                                        <div style={{ maxHeight: '400px', overflowY: 'auto', padding: '0 20px 20px' }}>
                                            <h4 style={{ fontSize: '14px', fontWeight: '600', marginBottom: '15px', color: '#333' }}>
                                                Recent News (Last 24 Hours)
                                            </h4>
                                            {articles.length === 0 ? (
                                                <div style={{ padding: '20px', textAlign: 'center', color: '#999' }}>
                                                    No news articles found in the last 24 hours
                                                </div>
                                            ) : (
                                                <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                                                    {articles.map((article, index) => (
                                                        <a
                                                            key={index}
                                                            href={article.url}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            style={{
                                                                display: 'flex',
                                                                gap: '12px',
                                                                padding: '12px',
                                                                backgroundColor: '#f8f9fa',
                                                                borderRadius: '8px',
                                                                textDecoration: 'none',
                                                                color: 'inherit',
                                                                transition: 'all 0.2s',
                                                                border: '1px solid #e0e0e0'
                                                            }}
                                                            onMouseEnter={(e) => {
                                                                e.currentTarget.style.backgroundColor = '#e9ecef';
                                                                e.currentTarget.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
                                                            }}
                                                            onMouseLeave={(e) => {
                                                                e.currentTarget.style.backgroundColor = '#f8f9fa';
                                                                e.currentTarget.style.boxShadow = 'none';
                                                            }}
                                                        >
                                                            {article.banner_image && (
                                                                <img
                                                                    src={article.banner_image}
                                                                    alt={article.title}
                                                                    style={{
                                                                        width: '80px',
                                                                        height: '60px',
                                                                        objectFit: 'cover',
                                                                        borderRadius: '4px',
                                                                        flexShrink: 0
                                                                    }}
                                                                    onError={(e) => {
                                                                        e.target.style.display = 'none';
                                                                    }}
                                                                />
                                                            )}
                                                            <div style={{ flex: 1, minWidth: 0 }}>
                                                                <div style={{
                                                                    fontSize: '13px',
                                                                    fontWeight: '600',
                                                                    marginBottom: '6px',
                                                                    color: '#333',
                                                                    lineHeight: '1.4',
                                                                    display: '-webkit-box',
                                                                    WebkitLineClamp: 2,
                                                                    WebkitBoxOrient: 'vertical',
                                                                    overflow: 'hidden'
                                                                }}>
                                                                    {article.title}
                                                                </div>
                                                                <div style={{ fontSize: '11px', color: '#666', display: 'flex', gap: '10px', alignItems: 'center' }}>
                                                                    <span>{article.source}</span>
                                                                    {article.time_published && (() => {
                                                                        try {
                                                                            // Alpha Vantage format: "20241217T143000"
                                                                            const timeStr = article.time_published;
                                                                            if (timeStr && timeStr.length >= 13) {
                                                                                const year = timeStr.substring(0, 4);
                                                                                const month = timeStr.substring(4, 6);
                                                                                const day = timeStr.substring(6, 8);
                                                                                const hour = timeStr.substring(9, 11);
                                                                                const minute = timeStr.substring(11, 13);
                                                                                // Format as YYYY-MM-DD HH:mm (space instead of T)
                                                                                return <span>• {`${year}-${month}-${day} ${hour}:${minute}`}</span>;
                                                                            }
                                                                        } catch (e) {
                                                                            return null;
                                                                        }
                                                                        return null;
                                                                    })()}
                                                                    {article.relevance_score !== undefined && article.relevance_score !== null && (
                                                                        <span>• Relevance: {(article.relevance_score * 100).toFixed(1)}%</span>
                                                                    )}
                                                                </div>
                                                            </div>
                                                        </a>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    </>
                                );
                            })()}
                        </div>
                    </div>
                </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default StockChart;