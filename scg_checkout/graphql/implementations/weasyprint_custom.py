from weasyprint import CSS, HTML


class PdfGenerator:


    def __init__(
        self,
        main_html,
        header_html=None,
        footer_html=None,
        base_url=None,
        side_margin=2,
        extra_vertical_margin=30,
        mt=None,
        mr=None,
        orientation=None
    ):
        self.main_html = main_html
        self.header_html = header_html
        self.footer_html = footer_html
        self.base_url = base_url
        self.side_margin = side_margin
        self.extra_vertical_margin = extra_vertical_margin
        self.mt = mt
        self.mr = mr
        self.orientation = orientation

    def _compute_overlay_element(self, element: str):
        html = HTML(
            string=getattr(self, f"{element}_html"),
            base_url=self.base_url,
        )
        overlay_layout = "@page {size: A4 %s; margin: 0;}" % (self.orientation)
        element_doc = html.render(stylesheets=[CSS(string=overlay_layout)])
        element_page = element_doc.pages[0]
        element_body = PdfGenerator.get_element(
            element_page._page_box.all_children(), "body"
        )
        element_body = element_body.copy_with_children(element_body.all_children())
        element_html = PdfGenerator.get_element(
            element_page._page_box.all_children(), element
        )
        if element == "header":
            element_height = element_html.height + 30
        if element == "footer":
            element_height = 30

        return element_body, element_height

    def _apply_overlay_on_main(self, main_doc, header_body=None, footer_body=None):
        for page in main_doc.pages:
            page_body = PdfGenerator.get_element(page._page_box.all_children(), "body")

            if header_body:
                page_body.children += header_body.all_children()
            if footer_body:
                page_body.children += footer_body.all_children()

    def render_pdf(self):
        if self.header_html:
            header_body, header_height = self._compute_overlay_element("header")
        else:
            header_body, header_height = None, 0
        if self.footer_html:
            footer_body, footer_height = self._compute_overlay_element("footer")
        else:
            footer_body, footer_height = None, 0

        margins = "{header_size}px {side_margin} {footer_size}px {side_margin}".format(
            header_size=header_height + self.extra_vertical_margin,
            footer_size=footer_height + self.extra_vertical_margin,
            side_margin=f"{self.side_margin}cm",
        )
        content_print_layout = (
            '@page {size: A4 %s; margin: %s;@top-right {font-size: 11px;margin-top: %s;margin-right: %s;content: "หน้า " counter(page) "/" counter(pages);}}'
            % (self.orientation, margins, self.mt, self.mr)
        )

        html = HTML(
            string=self.main_html,
            base_url=self.base_url,
        )
        main_doc = html.render(stylesheets=[CSS(string=content_print_layout)])

        if self.header_html or self.footer_html:
            self._apply_overlay_on_main(main_doc, header_body, footer_body)
        pdf = main_doc.write_pdf()

        return pdf

    @staticmethod
    def get_element(boxes, element):
        for box in boxes:
            if box.element_tag == element:
                return box
            return PdfGenerator.get_element(box.all_children(), element)
