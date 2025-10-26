import React, { useState, useEffect, useRef, useCallback } from 'react';
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
    const [loading, setLoading] = useState(false);
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
    
    const [chartConfig, setChartConfig] = useState({
        ticker: 'AAPL',
        interval: '1d',
        ma_options: 'sma',
        tech_ind: 'macd'
    });
    
    // Store time ranges from backend
    const [timeRanges, setTimeRanges] = useState([]);

    // base chart config
    const getBaseChartConfig = (height) => ({
        layout: {
            background: { type: ColorType.Solid, color: 'white' },
            textColor: 'black',
            fontFamily: 'Raleway, sans-serif',
            fontSize: 12,
        },
        grid: {
            // vertLines: { color: 'rgba(197, 203, 206, 0.5)' },
            // horzLines: { color: 'rgba(197, 203, 206, 0.5)' },
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
        },
        timeScale: {
            borderColor: 'rgba(197, 203, 206, 1)',
            timeVisible: true,
            secondsVisible: false,
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
        console.log('Sync called, range:', visibleRange);
        
        if (syncInProgress.current) {
            console.log('Sync blocked - already in progress');
            return;
        }
        
        syncInProgress.current = true;
        
        try {
            // 修复验证逻辑 - 支持字符串和数字格式的时间
            if (!visibleRange || 
                !visibleRange.from || 
                !visibleRange.to ||
                visibleRange.from === visibleRange.to) {
                console.log('Invalid range, skipping sync');
                return;
            }
            
            console.log('Valid range, syncing to other charts');
            
            allCharts.current.forEach((chart, index) => {
                if (chart && chart !== sourceChart && chart.timeScale) {
                    try {
                        console.log(`Syncing to chart ${index}`);
                        // Check if chart.timeScale() is valid before calling setVisibleRange
                        const timeScale = chart.timeScale();
                        if (timeScale && typeof timeScale.setVisibleRange === 'function') {
                            timeScale.setVisibleRange(visibleRange);
                        } else {
                            console.warn(`Chart ${index} timeScale is not valid`);
                        }
                    } catch (error) {
                        console.warn(`Failed to sync chart ${index}:`, error);
                    }
                }
            });
        } finally {
            // 立即重置，避免阻塞后续操作
                syncInProgress.current = false;
        }
    };

    // initialize three charts
    useEffect(() => {
        let charts = [];
        
        try {
            // initialize price chart
            if (priceChartRef.current) {
                console.log('Initializing price chart...');
                console.log('Chart container:', priceChartRef.current);
                console.log('Container width:', priceChartRef.current.clientWidth);
                
                priceChart.current = createChart(priceChartRef.current, {
                    ...getBaseChartConfig(400),
                    width: priceChartRef.current.clientWidth,
                });

                console.log('Price chart created:', priceChart.current);
                console.log('Chart has series method?', typeof priceChart.current.series === 'function');

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
                
                console.log('Candlestick series created:', candlestickSeries.current);
                charts.push(priceChart.current);
                
                // create vertical indicator line
                createVerticalLine(priceChartRef.current, 0);
            }

            // initialize volume chart
            if (volumeChartRef.current) {
                volumeChart.current = createChart(volumeChartRef.current, {
                    ...getBaseChartConfig(150),
                    width: volumeChartRef.current.clientWidth,
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
                            console.log(`Chart ${index} range changed:`, visibleRange); // debug log
                            syncTimeScale(chart, visibleRange);
                        });
                        

                    }
                });
            }, 100);

        } catch (error) {
            console.error('Error initializing charts:', error);
        }

        // window size adjustment handling
        const handleResize = () => {
            const chartConfigs = [
                { chart: priceChart.current, container: priceChartRef.current },
                { chart: volumeChart.current, container: volumeChartRef.current },
                { chart: technicalChart.current, container: technicalChartRef.current }
            ];
            
            chartConfigs.forEach(({ chart, container }) => {
                if (chart && container) {
                    try {
                        chart.applyOptions({ width: container.clientWidth });
                    } catch (error) {
                        console.warn('Error resizing chart:', error);
                    }
                }
            });
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
    const fetchStockData = async () => {
        setLoading(true);
        setError(null);
        
        try {
            const response = await axios.post('http://localhost:8000/api/stocks/' + chartConfig.ticker, {
                interval: chartConfig.interval,
                ma_options: chartConfig.ma_options,
                tech_ind: chartConfig.tech_ind
            });
            setStockData(response.data);
            
            // Extract and store time ranges from chart_config
            if (response.data.chart_config && response.data.chart_config.time_ranges) {
                setTimeRanges(response.data.chart_config.time_ranges);
            }
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to fetch stock data');
        } finally {
            setLoading(false);
        }
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
                    priceChart.current.subscribeCrosshairMove((param) => {
                        // handle crosshair event
                        console.log('Price chart crosshair:', param);
                        // ... event handling logic
                    });
                }
            }, 100);

        } catch (error) {
            console.error('Error updating charts:', error);
            setError('Failed to update charts: ' + error.message);
        }
    };

    const updatePriceChart = () => {
        if (!priceChart.current || !stockData.candlestick_data) {
            console.log('updatePriceChart: Missing chart or data', {
                hasChart: !!priceChart.current,
                hasData: !!stockData.candlestick_data
            });
            return;
        }

        console.log('updatePriceChart: Starting update', {
            chartElement: priceChartRef.current,
            chartWidth: priceChartRef.current?.clientWidth,
            chartHeight: priceChartRef.current?.clientHeight,
            dataLength: stockData.candlestick_data.length
        });

        try {
            // 1. clear all existing series (more thorough method)
            // method A: clear stored series references
            Object.values(maSeries.current).forEach(series => {
                if (series && priceChart.current) {
                    try {
                        priceChart.current.removeSeries(series);
                    } catch (error) {
                        console.warn('Error removing MA series:', error);
                    }
                }
            });
            maSeries.current = {};

            // method B: remove all series from chart to ensure clean state
            // Check if priceChart.current is valid and has series method
            if (priceChart.current && typeof priceChart.current.series === 'function') {
                const allSeries = priceChart.current.series();
                console.log('Before cleanup - Total series:', allSeries.length);
                console.log('Candlestick series reference:', candlestickSeries.current);
                
                // Don't remove any series, just clear MA series references
                // This prevents accidentally removing the candlestick series
                console.log('Skipping series removal to prevent candlestick series loss');
            } else {
                console.log('priceChart.current is not valid or series method not available');
                console.log('priceChart.current:', priceChart.current);
            }

            // 2. update candlestick data
            console.log('Setting candlestick data...');
            console.log('Candlestick series exists?', !!candlestickSeries.current);
            console.log('Candlestick data length:', stockData.candlestick_data.length);
            console.log('First candlestick item:', stockData.candlestick_data[0]);
            
            if (candlestickSeries.current) {
                console.log('Using existing candlestick series');
                candlestickSeries.current.setData(stockData.candlestick_data);
                console.log('Candlestick data set successfully');
                
                // Force chart to fit content
                priceChart.current.timeScale().fitContent();
                console.log('Chart time scale fitted to content');
            } else {
                console.log('Creating new candlestick series');
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
                console.log('New candlestick series created:', candlestickSeries.current);
                candlestickSeries.current.setData(stockData.candlestick_data);
                console.log('Candlestick data set on new series');
                
                // Force chart to fit content
                priceChart.current.timeScale().fitContent();
                console.log('Chart time scale fitted to content');
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
                        title: 'MACD',
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
                        title: 'Signal',
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
                        title: 'MACD Histogram',
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
                        title: 'RSI',
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
                            title: line.toUpperCase().replace('_LINE', ''),
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

    const handleConfigChange = (key, value) => {
        if (key === 'ticker') {
            // Filter stocks as user types
            filterStocks(value);
        }
        
        setChartConfig(prev => ({
            ...prev,
            [key]: value
        }));
    };

    // Handle stock selection from suggestions
    const handleStockSelect = (stock) => {
        setChartConfig(prev => ({
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
        } catch (error) {
            console.error('Error setting time range:', error);
        }
    };

    // Add a unified data update function
    const updateAllChartsData = (time, sourceIndex, sourceSeriesData) => {
        console.log('=== updateAllChartsData DEBUG ===');
        console.log('Time:', time);
        console.log('Source Index:', sourceIndex);
        console.log('SeriesData size:', sourceSeriesData ? sourceSeriesData.size : 0);
        
        const newCrosshairData = {
            price: null,
            volume: null,
            technical: null
        };
        
        // 1. Process Price Chart data - no matter which chart triggers, it must be processed
        if (stockData && stockData.ma_data) {
            console.log('Processing price chart data');
            
            const priceInfo = {
                time: time,
                candlestick: null,
                ma_values: {}
            };
            
            // get candlestick data - Get data from sourceSeriesData first, otherwise from stockData
            if (sourceIndex === 0 && candlestickSeries.current && sourceSeriesData.has(candlestickSeries.current)) {
                priceInfo.candlestick = sourceSeriesData.get(candlestickSeries.current);
                console.log('Got candlestick data from sourceSeriesData:', priceInfo.candlestick);
            } else {
                // find the corresponding candlestick data from stockData at the specified time
                const candlestickData = findDataAtTime(stockData.candlestick_data, time);
                if (candlestickData) {
                    priceInfo.candlestick = candlestickData;
                    console.log('Got candlestick data from stockData:', priceInfo.candlestick);
                } else {
                    console.log('No candlestick data found');
                }
            }
            
            // get moving average data - Get data from sourceSeriesData first, otherwise from stockData
            if (sourceIndex === 0 && maSeries.current) {
                console.log('Processing MA data from sourceSeriesData, keys:', Object.keys(maSeries.current));
                Object.entries(maSeries.current).forEach(([name, series]) => {
                    if (series && sourceSeriesData.has(series)) {
                        priceInfo.ma_values[name] = sourceSeriesData.get(series);
                        console.log(`Got MA data ${name} from sourceSeriesData:`, priceInfo.ma_values[name]);
                    } else {
                        console.log(`No MA data found for ${name} in sourceSeriesData`);
                    }
                });
            } else {
                // find the corresponding MA data from stockData at the specified time
                console.log('Processing MA data from stockData');
                
                // Only process the selected MA type
                const selectedMAType = chartConfig.ma_options.toLowerCase();
                if (stockData.ma_data[selectedMAType]) {
                    const dataArray = stockData.ma_data[selectedMAType];
                    
                    // Group data by period and find the data at the specified time
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
                    
                    // Find data for each period at the specified time
                    Object.entries(dataByPeriod).forEach(([period, data]) => {
                        const seriesName = `${selectedMAType.toUpperCase()}${period}`;
                        const maData = findDataAtTime(data, time);
                        if (maData) {
                            priceInfo.ma_values[seriesName] = maData;
                            console.log(`Got MA data ${seriesName} from stockData:`, priceInfo.ma_values[seriesName]);
                        } else {
                            console.log(`No MA data found for ${seriesName} in stockData`);
                        }
                    });
                }
                
                // Also process Bollinger Bands if they exist
                if (stockData.ma_data.bbands_upper) {
                    const upperData = findDataAtTime(stockData.ma_data.bbands_upper, time);
                    if (upperData) {
                        priceInfo.ma_values['BBANDS_UPPER'] = upperData;
                    }
                }
                if (stockData.ma_data.bbands_lower) {
                    const lowerData = findDataAtTime(stockData.ma_data.bbands_lower, time);
                    if (lowerData) {
                        priceInfo.ma_values['BBANDS_LOWER'] = lowerData;
                    }
                }
            }
            
            newCrosshairData.price = priceInfo;
        }
        
        // 2. Process Volume Chart data - no matter which chart triggers, it must be processed
        if (stockData && stockData.volume_data) {
            console.log('Processing volume chart data');
            
            let volumeData = null;
            
            // get data from sourceSeriesData first, otherwise from stockData
            if (sourceIndex === 1 && volumeSeries.current && sourceSeriesData.has(volumeSeries.current)) {
                const seriesData = sourceSeriesData.get(volumeSeries.current);
                console.log('Got volume data from sourceSeriesData:', seriesData);
                
                // Find the corresponding complete volume data from stockData, ensure the color field is correct
                const fullVolumeData = findDataAtTime(stockData.volume_data, time);
                if (fullVolumeData) {
                    // Use seriesData's value, but use fullVolumeData's color
                    volumeData = {
                        time: seriesData.time,
                        value: seriesData.value,
                        color: fullVolumeData.color  // Use complete color information
                    };
                    console.log('Combined volume data:', volumeData);
                } else {
                    volumeData = seriesData;
                }
            } else {
                // find the corresponding volume data from stockData at the specified time
                const foundVolumeData = findDataAtTime(stockData.volume_data, time);
                if (foundVolumeData) {
                    volumeData = foundVolumeData;
                    console.log('Got volume data from stockData:', volumeData);
                } else {
                    console.log('No volume data found');
                }
            }
            
            if (volumeData) {
                newCrosshairData.volume = {
                    time: time,
                    volume: volumeData
                };
            }
        }
        
        // 3. Process Technical Chart data - no matter which chart triggers, it must be processed
        if (stockData && stockData.technical_data) {
            console.log('Processing technical chart data');
            
            const technicalValues = {};
            
            // Create key mapping: technicalSeries.current's key -> stockData.technical_data's key
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
            
            // get data from sourceSeriesData first, otherwise from stockData
            if (sourceIndex === 2 && technicalSeries.current) {
                console.log('Processing technical data from sourceSeriesData');
                Object.entries(technicalSeries.current).forEach(([seriesKey, series]) => {
                    if (series && sourceSeriesData.has(series)) {
                        const dataKey = technicalKeyMapping[seriesKey] || seriesKey;
                        technicalValues[dataKey] = sourceSeriesData.get(series);
                        console.log(`Got technical data ${seriesKey} -> ${dataKey} from sourceSeriesData:`, technicalValues[dataKey]);
                    }
                });
            } else {
                // find the corresponding technical data from stockData at the specified time
                console.log('Processing technical data from stockData');
                Object.entries(stockData.technical_data).forEach(([name, data]) => {
                    const techData = findDataAtTime(data, time);
                    if (techData) {
                        technicalValues[name] = techData;
                        console.log(`Got technical data ${name} from stockData:`, technicalValues[name]);
                    } else {
                        console.log(`No technical data found for ${name} in stockData`);
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
        
        console.log('Final crosshair data:', newCrosshairData);
        setCrosshairData(newCrosshairData);
        console.log('=== END updateAllChartsData DEBUG ===');
    };

    // Add helper function to find data at a specified time
    const findDataAtTime = (dataArray, targetTime) => {
        if (!dataArray || !Array.isArray(dataArray)) return null;
        
        // Find the data point closest to the target time
        return dataArray.find(item => item.time === targetTime) || null;
    };

    return (
        <div className="multi-chart-container">
            {/* control panel */}
            <div className="chart-controls">
                <div className="control-group">
                    <label>Ticker:</label>
                    <div className="stock-search-container">
                    <input
                        type="text"
                        value={chartConfig.ticker}
                        onChange={(e) => handleConfigChange('ticker', e.target.value.toUpperCase())}
                            onFocus={() => {
                                if (chartConfig.ticker.length > 0) {
                                    filterStocks(chartConfig.ticker);
                                }
                            }}
                            onBlur={() => {
                                // Delay hiding suggestions to allow clicking
                                setTimeout(() => setShowStockSuggestions(false), 200);
                            }}
                        placeholder="Enter ticker"
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
                </div>

                <div className="control-group">
                    <label>Interval:</label>
                    <select
                        value={chartConfig.interval}
                        onChange={(e) => handleConfigChange('interval', e.target.value)}
                    >
                        <option value="1m">1 minute</option>
                        <option value="5m">5 minutes</option>
                        <option value="15m">15 minutes</option>
                        <option value="30m">30 minutes</option>
                        <option value="60m">1 hour</option>
                        <option value="1d">1 day</option>
                        <option value="1wk">1 week</option>
                        <option value="1mo">1 month</option>
                    </select>
                </div>

                <div className="control-group">
                    <label>Moving Average:</label>
                    <select
                        value={chartConfig.ma_options}
                        onChange={(e) => handleConfigChange('ma_options', e.target.value)}
                    >
                        <option value="">None</option>
                        <option value="sma">SMA</option>
                        <option value="ema">EMA</option>
                        <option value="wma">WMA</option>
                        <option value="dema">DEMA</option>
                        <option value="tema">TEMA</option>
                        <option value="kama">KAMA</option>
                    </select>
                </div>

                <div className="control-group">
                    <label>Technical Indicators:</label>
                    <select
                        value={chartConfig.tech_ind}
                        onChange={(e) => handleConfigChange('tech_ind', e.target.value)}
                    >
                        <option value="">None</option>
                        <option value="macd">MACD</option>
                        <option value="rsi">RSI</option>
                        <option value="kdj">KDJ</option>
                    </select>
                </div>

                <button 
                    onClick={fetchStockData} 
                    disabled={loading}
                    className="fetch-button"
                >
                    {loading ? 'Loading...' : 'Get Data'}
                </button>
            </div>

            {/* company info */}
            {stockData?.company_info && (
                <div className="company-info">
                    <h2>{stockData.company_info.longName || chartConfig.ticker}</h2>
                    <div className="company-details">
                        <span>Industry: {stockData.company_info.industry || 'N/A'}</span>
                        <span>Market Cap: {stockData.company_info.marketCap ? `$${(stockData.company_info.marketCap / 1e9).toFixed(2)}B` : 'N/A'}</span>
                        <span>P/E: {stockData.company_info.peRatio || 'N/A'}</span>
                    </div>
                    {/* add data note */} 
                    {chartConfig.interval === '1d' && (
                        <div className="data-note">
                            <span className="note-text">📊 Daily prices are adjusted for dividends and stock splits</span>
                        </div>
                    )}
                </div>
            )}

            {/* error info */}
            {error && (
                <div className="error-message">
                    Error: {error}
                </div>
            )}

            {/* multi chart container */}
            <div className="charts-wrapper">
                {/* price chart */}
                <div className="chart-section">
                    <div className="chart-title">Stock Price & Moving Averages</div>
                    
                    {/* Time Range Selector */}
                    {timeRanges.length > 0 && (
                        <div className="time-range-selector">
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
                    )}
                    
                    <div className="chart-container">
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
                                                        color: isHighlighted ? '#FFD700' : 'inherit'
                                                    }}
                                                >{seriesName}</span>
                                                <span 
                                                    className="legend-value"
                                                    style={{
                                                        fontWeight: 'bold',
                                                        color: isHighlighted ? '#FFD700' : 'inherit'
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
                </div>

                {/* volume chart */}
                <div className="chart-section">
                    <div className="chart-title">Volume</div>
                    <div className="chart-container">
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
                    <div className="chart-title">
                        Technical Indicators - {chartConfig.tech_ind.toUpperCase()}
                    </div>
                    <div className="chart-container">
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
            </div>
        </div>
    );
};

export default StockChart;