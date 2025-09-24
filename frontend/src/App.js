import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Area, AreaChart } from 'recharts';
import axios from 'axios';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const PerformanceChart = () => {
  const [performanceData, setPerformanceData] = useState(null);
  const [activeTimeframe, setActiveTimeframe] = useState('1Y');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [assetsInfo, setAssetsInfo] = useState(null);
  const [chartType, setChartType] = useState('area');

  const timeframes = [
    { label: '1M', value: '1M' },
    { label: '6M', value: '6M' },
    { label: '1Y', value: '1Y' },
    { label: 'ALL', value: 'ALL' }
  ];

  useEffect(() => {
    fetchAssetsInfo();
    fetchPerformanceData(activeTimeframe);
  }, [activeTimeframe]);

  const fetchAssetsInfo = async () => {
    try {
      const response = await axios.get(`${API}/assets/info`);
      setAssetsInfo(response.data);
    } catch (err) {
      console.error('Error fetching assets info:', err);
    }
  };

  const fetchPerformanceData = async (timeframe) => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${API}/performance/${timeframe}`);
      const { crypto_data, traditional_data } = response.data;
      
      // Combine and normalize data for the chart
      const combinedData = [];
      const maxLength = Math.max(crypto_data.length, traditional_data.length);
      
      for (let i = 0; i < maxLength; i++) {
        const cryptoPoint = crypto_data[i];
        const traditionalPoint = traditional_data[i];
        
        if (cryptoPoint && traditionalPoint) {
          combinedData.push({
            date: cryptoPoint.date,
            crypto: cryptoPoint.normalized_return,
            traditional: traditionalPoint.normalized_return,
            cryptoPrice: cryptoPoint.price,
            traditionalPrice: traditionalPoint.price
          });
        }
      }
      
      setPerformanceData(combinedData);
    } catch (err) {
      setError('Failed to fetch performance data');
      console.error('Error fetching performance data:', err);
    } finally {
      setLoading(false);
    }
  };

  const formatTooltipValue = (value, name) => {
    if (name === 'crypto') {
      return [`${value.toFixed(2)}%`, 'Bitcoin'];
    } else if (name === 'traditional') {
      return [`${value.toFixed(2)}%`, '60/40 Portfolio'];
    }
    return [value, name];
  };

  const formatXAxis = (tickItem) => {
    const date = new Date(tickItem);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const date = new Date(label).toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
      });
      
      return (
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-lg">
          <p className="text-gray-300 text-sm mb-2">{date}</p>
          {payload.map((entry, index) => (
            <p key={index} className="text-sm" style={{ color: entry.color }}>
              <span className="font-medium">
                {entry.name === 'crypto' ? 'Top 10 Crypto Portfolio' : '60/40 Portfolio'}:
              </span>
              <span className="ml-2 font-bold">
                {entry.value > 0 ? '+' : ''}{entry.value.toFixed(2)}%
              </span>
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  const renderChart = () => {
    if (chartType === 'area') {
      return (
        <AreaChart data={performanceData}>
          <defs>
            <linearGradient id="cryptoGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f7931a" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="#f7931a" stopOpacity={0.05}/>
            </linearGradient>
            <linearGradient id="traditionalGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.05}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis 
            dataKey="date" 
            tickFormatter={formatXAxis}
            stroke="#9ca3af"
            fontSize={12}
          />
          <YAxis 
            stroke="#9ca3af"
            fontSize={12}
            tickFormatter={(value) => `${value}%`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend 
            wrapperStyle={{ paddingTop: '20px' }}
            iconType="line"
          />
          <Area
            type="monotone"
            dataKey="crypto"
            stroke="#f7931a"
            strokeWidth={2}
            fill="url(#cryptoGradient)"
            name="Top 10 Crypto Portfolio"
          />
          <Area
            type="monotone"
            dataKey="traditional"
            stroke="#3b82f6"
            strokeWidth={2}
            fill="url(#traditionalGradient)"
            name="60/40 Portfolio"
          />
        </AreaChart>
      );
    } else {
      return (
        <LineChart data={performanceData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis 
            dataKey="date" 
            tickFormatter={formatXAxis}
            stroke="#9ca3af"
            fontSize={12}
          />
          <YAxis 
            stroke="#9ca3af"
            fontSize={12}
            tickFormatter={(value) => `${value}%`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend 
            wrapperStyle={{ paddingTop: '20px' }}
            iconType="line"
          />
          <Line
            type="monotone"
            dataKey="crypto"
            stroke="#f7931a"
            strokeWidth={3}
            dot={false}
            name="Top 10 Crypto Portfolio"
          />
          <Line
            type="monotone"
            dataKey="traditional"
            stroke="#3b82f6"
            strokeWidth={3}
            dot={false}
            name="60/40 Portfolio"
          />
        </LineChart>
      );
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-300">Loading performance data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-500 text-xl mb-4">⚠️ Error</div>
          <p className="text-gray-300">{error}</p>
          <button 
            onClick={() => fetchPerformanceData(activeTimeframe)}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <h1 className="text-3xl font-bold text-center">
            Portfolio Performance: Crypto vs Traditional Assets
          </h1>
          <p className="text-gray-400 text-center mt-2">
            Comparing Bitcoin with a 60/40 Traditional Portfolio (S&P 500 + Bonds)
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex flex-col sm:flex-row justify-between items-center mb-6 space-y-4 sm:space-y-0">
          {/* Timeframe Buttons */}
          <div className="flex space-x-2">
            {timeframes.map((timeframe) => (
              <button
                key={timeframe.value}
                onClick={() => setActiveTimeframe(timeframe.value)}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  activeTimeframe === timeframe.value
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                {timeframe.label}
              </button>
            ))}
          </div>

          {/* Chart Type Toggle */}
          <div className="flex space-x-2">
            <button
              onClick={() => setChartType('area')}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                chartType === 'area'
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              Area Chart
            </button>
            <button
              onClick={() => setChartType('line')}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                chartType === 'line'
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              Line Chart
            </button>
          </div>
        </div>

        {/* Performance Stats */}
        {performanceData && performanceData.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <h3 className="text-lg font-semibold mb-2 text-orange-400">Bitcoin Performance</h3>
              <div className="text-2xl font-bold">
                {performanceData[performanceData.length - 1]?.crypto > 0 ? '+' : ''}
                {performanceData[performanceData.length - 1]?.crypto.toFixed(2)}%
              </div>
              <p className="text-gray-400 text-sm mt-1">Total Return ({activeTimeframe})</p>
            </div>
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <h3 className="text-lg font-semibold mb-2 text-blue-400">60/40 Portfolio Performance</h3>
              <div className="text-2xl font-bold">
                {performanceData[performanceData.length - 1]?.traditional > 0 ? '+' : ''}
                {performanceData[performanceData.length - 1]?.traditional.toFixed(2)}%
              </div>
              <p className="text-gray-400 text-sm mt-1">Total Return ({activeTimeframe})</p>
            </div>
          </div>
        )}

        {/* Chart */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="h-96">
            {performanceData && (
              <ResponsiveContainer width="100%" height="100%">
                {renderChart()}
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Asset Information */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-lg font-semibold mb-3 text-orange-400">Bitcoin (BTC)</h3>
            <p className="text-gray-300 text-sm">
              The world's first and largest cryptocurrency by market capitalization. Known for its high volatility and potential for significant returns.
            </p>
          </div>
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-lg font-semibold mb-3 text-blue-400">60/40 Portfolio</h3>
            <p className="text-gray-300 text-sm">
              A traditional investment strategy allocating 60% to stocks (S&P 500) and 40% to bonds (20+ Year Treasury). Designed for balanced risk and return.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

function App() {
  return (
    <div className="App">
      <PerformanceChart />
    </div>
  );
}

export default App;