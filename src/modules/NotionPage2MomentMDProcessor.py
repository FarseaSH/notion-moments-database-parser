from datetime import datetime
from .NotionBlockTreeTranslator import NotionBlockTreeTranslator, NotionBlockTreeTranlatedResult
from .notion_modules.NotionClient import NotionClient


from dataclasses import dataclass
from datetime import datetime
from textwrap import dedent


@dataclass
class NotionPageProperties:
    """
    Notion 页面属性
    """

    page_id: str
    created_time: datetime
    author: str
    signature: str
    tags: list[str]
    note: str
    resource: str
    resource_text: str
    resource_image: str


class NotionPage2MomentMDProcessor:
    """
    负责页面id 到 最后 md内容的生成
    
    """

    TIME_FORMAT = r'%Y-%m-%dT%H:%M:%S.000%z'
    

    def __init__(self, raw_notion_page_meta_info: dict, client: NotionClient) -> None:
        self.notion_page_properties = self._parse_notion_page_properties(raw_notion_page_meta_info)
        self.children_block_tree = None
        self.notion_block_tree_tranlated_result: 'None|NotionBlockTreeTranlatedResult' = None
        self.md_result: 'None | str' = None
        self.client = client


    def process(self):
        self._fetch_notion_block_tree()
        self._parse_block_tree()
        self._gen_md_result()
    

    def get_result(self) -> 'str':
        assert self.md_result is not None
        return self.md_result
    

    @staticmethod
    def _parse_notion_page_properties(raw_notion_page_meta_info: dict):
        # TODO refector this by using dataclass

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
        self.children_block_tree = self.client.fetch_page_block_tree(self.notion_page_properties.page_id)


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
