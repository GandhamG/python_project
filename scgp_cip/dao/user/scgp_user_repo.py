from scgp_user_management.models import ScgpUser


class ScgpUserRepo:
    @classmethod
    def get_by_user_id(cls, user_id):
        return ScgpUser.objects.filter(user__id=user_id).first()
