# %%
from pathlib import Path

import os

from .modules.notion_modules.NotionClient import NotionClient
from .modules.NotionPage2MomentMDProcessor import NotionPage2MomentMDProcessor

notion_secret = os.environ.get("NOTION_SECRET")
notion_database_id = os.environ.get("NOTION_DATABASE_ID")
client = NotionClient(notion_secret, notion_database_id)


# %%
def main():
    Path("./content").mkdir(parents=True, exist_ok=True)

    notion_page_meta_infos = client.fetch_all_database_pages(notion_database_id)
    print(f"total num of pages: {len(notion_page_meta_infos)}")

    for notion_page_meta_info in notion_page_meta_infos:
        processor = NotionPage2MomentMDProcessor(raw_notion_page_meta_info=notion_page_meta_info,
                                            client=client)
        processor.process()
        
        created_time = processor.notion_page_properties.created_time
        page_id = processor.notion_page_properties.page_id
        file_name: str = f"{created_time.strftime(r'%Y%m%d_%H%M')}-{page_id[:6]}.md"
        with open(f"content/{file_name}", encoding="utf-8", mode="w") as f:
            f.write(processor.get_result())


if __name__ == "__main__":
    main()

