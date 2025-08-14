import random
import json
from datetime import datetime, timedelta
from models import Trade, User
from app import db
import logging

logger = logging.getLogger(__name__)

def generate_sample_portfolio_data(user_id: int, num_trades: int = 50):
    """Generate sample trading data for portfolio analytics testing"""
    try:
        from app import app
        with app.app_context():
            # Sample symbols and strategies
            symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA', 'SPY', 'QQQ', 'BTC-USD', 'ETH-USD']
            strategies = ['manual', 'wheel', 'collar', 'ai']
            providers = ['schwab', 'coinbase', 'etrade']
            sides = ['buy', 'sell']
            
            trades_created = 0
            
            for i in range(num_trades):
                # Random trade parameters
                symbol = random.choice(symbols)
                strategy = random.choice(strategies)
                provider = random.choice(providers)
                side = random.choice(sides)
                
                # Generate realistic quantities and prices
                if symbol in ['BTC-USD', 'ETH-USD']:
                    quantity = round(random.uniform(0.01, 1.0), 4)
                    price = random.uniform(20000, 50000) if symbol == 'BTC-USD' else random.uniform(1500, 3500)
                else:
                    quantity = random.randint(1, 100)
                    price = random.uniform(50, 500)
                
                amount = quantity * price
                
                # Generate P&L for executed trades
                if random.random() > 0.1:  # 90% execution rate
                    status = 'executed'
                    # Generate realistic P&L (60% win rate)
                    if random.random() < 0.6:  # Winning trade
                        pnl = random.uniform(10, amount * 0.15)
                    else:  # Losing trade
                        pnl = -random.uniform(5, amount * 0.08)
                    
                    execution_details = json.dumps({
                        'pnl': round(pnl, 2),
                        'execution_price': round(price, 2),
                        'fees': round(random.uniform(0.5, 5.0), 2)
                    })
                    executed_at = datetime.utcnow() - timedelta(days=random.randint(0, 90))
                else:
                    status = 'pending'
                    execution_details = None
                    executed_at = None
                
                # Create trade record
                trade = Trade(
                    user_id=user_id,
                    provider=provider,
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=price,
                    amount=amount,
                    status=status,
                    trade_type='market',
                    strategy=strategy,
                    natural_language_prompt=f"Sample {strategy} trade for {symbol}",
                    execution_details=execution_details,
                    created_at=datetime.utcnow() - timedelta(days=random.randint(0, 90)),
                    executed_at=executed_at,
                    is_simulation=False
                )
                
                db.session.add(trade)
                trades_created += 1
            
            db.session.commit()
            logger.info(f"Generated {trades_created} sample trades for user {user_id}")
            
            return {
                'success': True,
                'trades_created': trades_created,
                'message': f'Successfully generated {trades_created} sample trades'
            }
            
    except Exception as e:
        logger.error(f"Error generating sample data: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def clear_sample_data(user_id: int):
    """Clear all sample trading data for user"""
    try:
        from app import app
        with app.app_context():
            deleted_count = Trade.query.filter_by(user_id=user_id).delete()
            db.session.commit()
            
            logger.info(f"Cleared {deleted_count} trades for user {user_id}")
            
            return {
                'success': True,
                'deleted_count': deleted_count,
                'message': f'Successfully cleared {deleted_count} trades'
            }
            
    except Exception as e:
        logger.error(f"Error clearing sample data: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }