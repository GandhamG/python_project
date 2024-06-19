# import base64
# import shutil

# import openpyxl
# from django.core.files.storage import default_storage

# from saleor.graphql.tests.utils import get_graphql_content
# from scg_checkout.graphql.implementations.materials import transform_data_for_export
# from scg_checkout.models import AlternativeMaterialOs
# from scg_checkout.tests.operations import EXPORT_ALTERNATIVE_MATERIAL


# def test_export_alternative_material(
#     staff_api_client,
#     scg_alternative_material_os,
#     media_root,
#     settings,
#     tmpdir,
# ):
#     file_name = "export_files/alternative_material.xlsx"
#     # assert response
#     response = staff_api_client.post_graphql(
#         EXPORT_ALTERNATIVE_MATERIAL,
#     )
#     target_data = get_graphql_content(response)["data"]["exportAlternativeMaterial"]
#     assert target_data["fileName"] == file_name.split("/")[-1]

#     with open(default_storage.path(file_name), "rb") as exported_file:
#         base64_str = base64.b64encode(exported_file.read())
#         assert target_data["exportedFileBase64"] == base64_str.decode("utf-8")

#     # assert exported file content
#     wb_obj = openpyxl.load_workbook(default_storage.path(file_name))

#     sheet_obj = wb_obj.active
#     max_col = sheet_obj.max_column
#     max_row = sheet_obj.max_row

#     # assert headers
#     headers = [sheet_obj.cell(row=1, column=i).value for i in range(1, max_col + 1)]
#     expected_headers = [
#         "Sale Org.",
#         "Sold to code",
#         "Material - Own",
#         "Material - OS",
#         "Dia",
#         "Type",
#         "Priority",
#     ]
#     assert headers == expected_headers

#     # assert row count
#     expected_count = AlternativeMaterialOs.objects.count()
#     assert max_row - 1 == expected_count

#     # assert each row
#     actual_rows = []
#     for i in range(2, max_row + 1):
#         row = []
#         for j in range(1, max_col + 1):
#             row.append(sheet_obj.cell(row=i, column=j).value)
#         actual_rows.append(row)

#     fields = (
#         "alternative_material__sales_organization__code",
#         "alternative_material__sold_to__code",
#         "alternative_material__material_own__code",
#         "material_os__code",
#         "material_os__dia",
#         "alternative_material__type",
#         "priority",
#         "alternative_material__material_own__grade_gram",
#         "material_os__grade_gram",
#     )
#     expected_rows = transform_data_for_export(
#         AlternativeMaterialOs.objects.values_list(*fields)
#     )

#     for row in actual_rows:
#         assert row in expected_rows
#     shutil.rmtree(tmpdir)
