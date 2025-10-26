import React from 'react';
import StockChart from './components/StockChart';
import MatrixBackground from './components/MatrixBackground';
import './components/StockChart.css';

function App() {
    return (
        <div className="App">
            <MatrixBackground />
            <header className="App-header">
                <h1>Stock Matrix</h1>
                <p>See Through The Market</p>
            </header>
            <main>
                <StockChart />
            </main>
        </div>
    );
}

export default App;