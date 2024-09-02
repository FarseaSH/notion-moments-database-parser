# %%
from notion_client import Client
from collections import namedtuple
from datetime import datetime
from textwrap import dedent
from pathlib import Path

import os

notion_secret = os.environ.get("NOTION_SECRET")
notion_database_id = os.environ.get("NOTION_DATABASE_ID")
client = Client(auth=notion_secret)


def fetch_all_notion_children_blocks(notion_page_id: str) -> 'list[dict]':
    has_more, start_cursor = True, None
    result = []
    while has_more:
        resp: dict = client.blocks.children.list(notion_page_id, start_cursor=start_cursor)
        result.extend(resp['results'])
        has_more = resp['has_more']
        start_cursor = resp['next_cursor']
    
    return result


NOTION_DATABASE_FILTER = {
    "property": "Publish",
    "select": {
        "equals": "Yes"
    }
}

def fetch_all_notion_database_pages(notion_database_id: str) -> 'list[dict]':
    has_more, start_cursor = True, None
    result = []
    while has_more:
        resp: dict = client.databases.query(notion_database_id, filter=NOTION_DATABASE_FILTER, start_cursor=start_cursor)
        result.extend(resp['results'])
        has_more = resp['has_more']
        start_cursor = resp['next_cursor']
    
    return result


class NotionBlockTree:
    def __init__(self, notion_id: str, val: 'dict|None') -> None:
        self.notion_id: str = notion_id
        self.val: 'dict|None' = val
        self.children_block: 'None|NotionBlockTree' = None
        self.next_block: 'None|NotionBlockTree' = None


class NotionBlockTreeFetcher:
    """
    用于给定某个 notion page 的 id，生成对应的 notion block树结构
    """
    def __init__(self, root_notion_id: str) -> None:
        self.root_block: 'NotionBlockTree' = NotionBlockTree(root_notion_id, None)
        self.blocks_to_query_children: 'list[NotionBlockTree]' = [self.root_block]
        self.is_fetched = False


    def fetch(self):
        while self.blocks_to_query_children:
            current_block_fetch_children = self.blocks_to_query_children.pop(0)
            children_blocks = fetch_all_notion_children_blocks(current_block_fetch_children.notion_id)

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


NotionBlockTreeTranlatedResult = namedtuple("NotionBlockTreeTranlatedResult", [
    "md_text",  # str
    "images"  # list[str]
])

class NotionBlockTreeTranslator:
    _LIST_ITEM = {"numbered_list_item", "bulleted_list_item"}  # 列表的解析需要特殊处理

    def __init__(self, block_tree: 'NotionBlockTree') -> None:
        self.block_tree = block_tree
        self.block_to_parse_queue: 'list[NotionBlockTree]' = []
        self.md_paragraphs: 'list[str]' = []
        self.images = []


    def translate(self) -> 'NotionBlockTreeTranlatedResult':
        self.block_to_parse_queue.append(self.block_tree)
        while self.block_to_parse_queue:
            tree_node = self.block_to_parse_queue.pop(0)
            notion_block_dict = tree_node.val

            if notion_block_dict is None:
                pass
            elif notion_block_dict['type'] in self._LIST_ITEM:
                self._parse_list_item(tree_node=tree_node)
            elif notion_block_dict['type'] == "paragraph": 
                self._parse_paragraph(notion_block_dict=notion_block_dict)
            elif notion_block_dict['type'] == "image": 
                self._parse_image(notion_block_dict=notion_block_dict)
            elif notion_block_dict['type'] == "code":
                self._parse_code(notion_block_dict=notion_block_dict)
            elif notion_block_dict['type'] == "quote":
                self._parse_quote(notion_block_dict=notion_block_dict)


            if notion_block_dict is not None and notion_block_dict['type'] in self._LIST_ITEM: continue

            if tree_node.next_block is not None: self.block_to_parse_queue.insert(0, tree_node.next_block)
            if tree_node.children_block is not None: self.block_to_parse_queue.insert(0, tree_node.children_block)


        return NotionBlockTreeTranlatedResult(md_text="\n\n".join(self.md_paragraphs), images=self.images)


    def _parse_list_item(self, tree_node: 'NotionBlockTree'):
        result: 'list[str]' = []

        def dfs(node: 'NotionBlockTree', index_level: int, numbered_list_number: int):
            """
            只解析 {"numbered_list_item", "bulleted_list_item"}        

            index_level: 从 0 开始
            numbered_list_number: 从 1 开始，记录序号列表当前的序号
            """

            notion_block_dict = node.val
            if notion_block_dict is None or notion_block_dict['type'] not in self._LIST_ITEM:
                return node

            if notion_block_dict['type'] == 'numbered_list_item':
                _content = self._extract_rich_text(notion_block_dict['numbered_list_item']['rich_text'])
                result.append(" " * 4 * index_level + f"{numbered_list_number}. {_content}")
                numbered_list_number += 1
            else:  # bulleted_list_item
                _content = self._extract_rich_text(notion_block_dict['bulleted_list_item']['rich_text'])
                result.append(" " * 4 * index_level + f"- {_content}")

            if node.children_block is not None:
                dfs(node.children_block, index_level + 1, 1)

            if node.next_block is not None:
                next_node = dfs(node.next_block, index_level, numbered_list_number)
            else:
                next_node = None

            return next_node

        next_node = dfs(tree_node, 0, 1)
        self.md_paragraphs.append("\n".join(result))
        if next_node is not None: self.block_to_parse_queue.insert(0, next_node)


    def _parse_paragraph(self, notion_block_dict: dict):
        self.md_paragraphs.append(
            self._extract_rich_text(notion_block_dict['paragraph']['rich_text'])
        )


    def _parse_image(self, notion_block_dict: dict):
        url = notion_block_dict['image']['file']['url'] if 'file' in notion_block_dict['image'] \
                else notion_block_dict['image']['external']['url']
        self.images.append((url))
    

    def _parse_code(self, notion_block_dict: dict):
        code = notion_block_dict['code']
        language = code.get("language", "")
        code_text = "".join(rich_text_part['plain_text'] for rich_text_part in code['rich_text'])
        
        self.md_paragraphs.append(f"""```{language}\n{code_text}\n```""")


    def _parse_quote(self, notion_block_dict: dict):
        rich_text_extracted = self._extract_rich_text(notion_block_dict['quote']['rich_text'])
        quote_result = "\n>\n".join("> " + line for line in rich_text_extracted.split('\n'))
        self.md_paragraphs.append(quote_result)


    @staticmethod
    def _extract_rich_text(rich_text: 'list[dict]', only_plain_text=False) -> str:
        result: 'list[str]' = []
        for rich_text_part in rich_text:
            text = rich_text_part['plain_text']

            if only_plain_text:
                result.append(text)
                continue

            if rich_text_part['annotations']['bold']: text = f"**{text}**"
            if rich_text_part['annotations']['italic']: text = f"*{text}*"
            if rich_text_part['annotations']['strikethrough']: text = f"~~{text}~~"
            if rich_text_part['annotations']['code']: text = f"`{text}`"
            if 'href' in rich_text_part and rich_text_part['href']:
                text = f"[{text}]({rich_text_part['href']})"

            result.append(text)
        
        return "".join(result)



NotionPageProperties = namedtuple("NotionPageProperties", [
    "page_id",  # str
    "created_time",  # datetime
    "author",  # str
    "signature",  # str
    "tags",  # list[str]
    "note",  # str
    "resource",  # str
    "resource_text",  # str
    "resource_image",  # str
])

class NotionPage2MomentMDProcessor:
    """
    负责页面id 到 最后 md内容的生成
    
    """

    TIME_FORMAT = r'%Y-%m-%dT%H:%M:%S.000%z'
    

    def __init__(self, raw_notion_page_meta_info: dict) -> None:
        self.notion_page_properties = self._parse_notion_page_properties(raw_notion_page_meta_info)
        self.children_block_tree = None
        self.notion_block_tree_tranlated_result: 'None|NotionBlockTreeTranlatedResult' = None
        self.md_result: 'None | str' = None


    def process(self):
        self._fetch_notion_block_tree()
        self._parse_block_tree()
        self._gen_md_result()
    

    def get_result(self) -> 'str':
        assert self.md_result is not None
        return self.md_result
    

    @staticmethod
    def _parse_notion_page_properties(raw_notion_page_meta_info: dict):
        page_id = raw_notion_page_meta_info['id']
        # name = "".join(rich_text_part['plain_text'] for rich_text_part in raw_notion_page_meta_info['properties']['Name']['title'])
        signature = "".join(rich_text_part['plain_text'] for rich_text_part in raw_notion_page_meta_info['properties']['Signature']['rich_text'])
        resource = "".join(rich_text_part['plain_text'] for rich_text_part in raw_notion_page_meta_info['properties']['Resource']['rich_text'])
        resource_text = "".join(rich_text_part['plain_text'] for rich_text_part in raw_notion_page_meta_info['properties']['Resource Text']['rich_text'])
        resource_image = "".join(rich_text_part['plain_text'] for rich_text_part in raw_notion_page_meta_info['properties']['Resource Image']['rich_text'])

        if raw_notion_page_meta_info['properties']['Date']['date']:
            created_time = datetime.strptime(raw_notion_page_meta_info['properties']['Date']['date']['start'], NotionPage2MomentMDProcessor.TIME_FORMAT)
        else:
            created_time = datetime.strptime(raw_notion_page_meta_info['created_time'], NotionPage2MomentMDProcessor.TIME_FORMAT)

        tags = [tag['name'] for tag in raw_notion_page_meta_info['properties']['Tags']['multi_select']]

        if "Note" in raw_notion_page_meta_info['properties']:
            note = "".join(rich_text_part['plain_text'] for rich_text_part in raw_notion_page_meta_info['properties']['Note']['rich_text'])
        else:
            note = None
        
        return NotionPageProperties(
            page_id=page_id,
            created_time=created_time,
            author=None,
            signature=signature,
            tags=tags,
            note=note,
            resource=resource,
            resource_text=resource_text,
            resource_image=resource_image,
        )


    def _fetch_notion_block_tree(self):
        nbtf = NotionBlockTreeFetcher(self.notion_page_properties.page_id)
        nbtf.fetch()
        self.children_block_tree = nbtf.get_result()


    def _parse_block_tree(self):
        assert self.children_block_tree is not None
        nbp = NotionBlockTreeTranslator(self.children_block_tree)
        self.notion_block_tree_tranlated_result = nbp.translate()


    def _gen_md_result(self):
        assert self.notion_block_tree_tranlated_result is not None       

        _tag_part = "\n".join(f"  - {tag}" for tag in self.notion_page_properties.tags)
        _pictures_part = "\n".join(f"  - {image_url}" for image_url in self.notion_block_tree_tranlated_result.images)

        # todo fix possible quotation mark error
        front_matter_part = dedent(
            f"""
            ---
            top:
            name: "{self.notion_page_properties.author if self.notion_page_properties.author else ''}"
            avatar:
            signature: "{self.notion_page_properties.signature if self.notion_page_properties.signature else ''}"

            date: {self.notion_page_properties.created_time.strftime(r'%Y-%m-%dT%H:%M:%S%z')[:-2] + ":00"}

            tags:
            {{tag_part}}

            pictures:
            {{picture_part}}

            link: {'"' + self.notion_page_properties.resource + '"' if self.notion_page_properties.resource else ''}
            link_text: {'"' + self.notion_page_properties.resource_text + '"' if self.notion_page_properties.resource_text else ''}
            link_logo: 

            note: "{self.notion_page_properties.note}"
            ---
            """
        )  \
        .strip(" \n") \
        .format(tag_part=_tag_part, picture_part=_pictures_part)

        self.md_result = front_matter_part + "\n" + self.notion_block_tree_tranlated_result.md_text


# %%
def main():
    Path("./content").mkdir(parents=True, exist_ok=True)

    notion_page_meta_infos = fetch_all_notion_database_pages(notion_database_id)
    print(f"total num of pages: {len(notion_page_meta_infos)}")

    for notion_page_meta_info in notion_page_meta_infos:
        processor = NotionPage2MomentMDProcessor(raw_notion_page_meta_info=notion_page_meta_info)
        processor.process()
        
        created_time = processor.notion_page_properties.created_time
        page_id = processor.notion_page_properties.page_id
        file_name: str = f"{created_time.strftime(r'%Y%m%d_%H%M')}-{page_id[:6]}.md"
        with open(f"content/{file_name}", encoding="utf-8", mode="w") as f:
            f.write(processor.get_result())


if __name__ == "__main__":
    main()

