import json
import os
import logging
from db_manager import DatabaseManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def migrate():
    if not os.path.exists('processed.json'):
        logging.info("No processed.json found. Nothing to migrate.")
        return

    db = DatabaseManager()
    
    try:
        with open('processed.json', 'r') as f:
            processed_data = json.load(f)
            
        logging.info(f"Found {len(processed_data)} items in processed.json")
        
        migrated_count = 0
        for item_id, status in processed_data.items():
            if status:
                # Since the old format didn't have show_ids, we default to 'default_show'
                # or we can try to infer it if we had more info. 
                # For migration, we'll mark them as processed for all shows or just a legacy show.
                # Let's use 'legacy' as the show_id for migrated items.
                if db.mark_processed(show_id='legacy', article_id=item_id):
                    migrated_count += 1
        
        logging.info(f"Successfully migrated {migrated_count} items to SQLite.")
        
        # Rename the old file instead of deleting it to be safe
        os.rename('processed.json', 'processed.json.bak')
        logging.info("Renamed processed.json to processed.json.bak")

    except Exception as e:
        logging.error(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
