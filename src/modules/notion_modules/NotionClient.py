from notion_client import Client
import os

from .NotionBlockTree import NotionBlockTree

class NotionClient:
    """Notion API 客户端封装类"""
    
    # 默认的数据库过滤器
    DEFAULT_DATABASE_FILTER = {
        "property": "Publish",
        "select": {
            "equals": "Yes"
        }
    }
    
    def __init__(self, notion_secret: str = None, notion_database_id: str = None):
        """
        初始化 NotionClient
        
        Args:
            notion_secret: Notion API 密钥，如果不提供则从环境变量 NOTION_SECRET 获取
            notion_database_id: Notion 数据库 ID，如果不提供则从环境变量 NOTION_DATABASE_ID 获取
        """
        self.notion_secret = notion_secret or os.environ.get("NOTION_SECRET")
        self.notion_database_id = notion_database_id or os.environ.get("NOTION_DATABASE_ID")
        
        if not self.notion_secret:
            raise ValueError("Notion secret is required. Please provide it or set NOTION_SECRET environment variable.")
        
        self.client = Client(auth=self.notion_secret)
    
    def fetch_all_children_blocks(self, notion_page_id: str) -> list[dict]:
        """
        获取指定 Notion 页面的所有子块
        
        Args:
            notion_page_id: Notion 页面 ID
            
        Returns:
            包含所有子块信息的字典列表
        """
        has_more, start_cursor = True, None
        result = []
        
        while has_more:
            resp: dict = self.client.blocks.children.list(
                notion_page_id, 
                start_cursor=start_cursor
            )
            result.extend(resp['results'])
            has_more = resp['has_more']
            start_cursor = resp['next_cursor']
        
        return result
    
    def fetch_all_database_pages(self, 
                                notion_database_id: str = None, 
                                filter_config: dict = None) -> list[dict]:
        """
        获取数据库中所有符合过滤条件的页面
        
        Args:
            notion_database_id: Notion 数据库 ID，如果不提供则使用初始化时的 database_id
            filter_config: 过滤器配置，如果不提供则使用默认过滤器
            
        Returns:
            包含所有符合条件页面信息的字典列表
        """
        database_id = notion_database_id or self.notion_database_id
        if not database_id:
            raise ValueError("Database ID is required. Please provide it or set NOTION_DATABASE_ID environment variable.")
        
        filter_config = filter_config or self.DEFAULT_DATABASE_FILTER
        
        has_more, start_cursor = True, None
        result = []
        
        while has_more:
            resp: dict = self.client.databases.query(
                database_id, 
                filter=filter_config, 
                start_cursor=start_cursor
            )
            result.extend(resp['results'])
            has_more = resp['has_more']
            start_cursor = resp['next_cursor']
        
        return result
    

    def fetch_page_block_tree(self, page_id: str) -> NotionBlockTree:
        """
        获取指定页面的正文所有block，以一个NotionBlockTree的数据结构存储
        """
        nbtf = _NotionBlockTreeFetcher(page_id, self)
        nbtf.fetch()
        return nbtf.get_result()

    
    # def get_page(self, page_id: str) -> dict:
    #     """
    #     获取指定页面的详细信息
        
    #     Args:
    #         page_id: 页面 ID
            
    #     Returns:
    #         页面信息字典
    #     """
    #     return self.client.pages.retrieve(page_id)
    
    # def get_database(self, database_id: str = None) -> dict:
    #     """
    #     获取数据库的详细信息
        
    #     Args:
    #         database_id: 数据库 ID，如果不提供则使用初始化时的 database_id
            
    #     Returns:
    #         数据库信息字典
    #     """
    #     database_id = database_id or self.notion_database_id
    #     if not database_id:
    #         raise ValueError("Database ID is required.")
        
    #     return self.client.databases.retrieve(database_id)
    


class _NotionBlockTreeFetcher:
    """
    用于给定某个 notion page 的 id，生成对应的 notion block树结构
    """
    def __init__(self, root_notion_id: str, client: NotionClient) -> None:
        self.root_block: 'NotionBlockTree' = NotionBlockTree(root_notion_id, None)
        self.blocks_to_query_children: 'list[NotionBlockTree]' = [self.root_block]
        self.is_fetched = False
        self.client = client


    def fetch(self):
        while self.blocks_to_query_children:
            current_block_fetch_children = self.blocks_to_query_children.pop(0)
            children_blocks = self.client.fetch_all_children_blocks(current_block_fetch_children.notion_id)

            blk = dummy = NotionBlockTree("", None)
            for children_block in children_blocks:
                _next_block = NotionBlockTree(notion_id=children_block['id'], val=children_block)

                if children_block['has_children']:
                    self.blocks_to_query_children.append(_next_block)
                
                blk.next_block = _next_block
                blk = blk.next_block

            current_block_fetch_children.children_block = dummy.next_block
        
        self.is_fetched = True


    def get_result(self) -> 'NotionBlockTree':
        if not self.is_fetched: raise AssertionError("`fetch` method has not run.")
        return self.root_block
