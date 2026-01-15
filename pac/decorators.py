from django.contrib.auth.models import Group


def check_group(user,group_name):
    if user.is_authenticated:
        return user.groups.filter(name=group_name).exists()
    return False


def is_admin(user):
    return user.is_superuser or check_group(user,'admin')

def is_simple(user):
    return check_group(user,'simple_user')

def is_greffier(user):
    return check_group(user,'greffier')

def is_procureur(user):
    return check_group(user,'procureur')

def is_opj(user):
    return check_group(user,'opj')

def is_public(user):
    return check_group(user,'public')

def is_dcn(user):
    return check_group(user,'DCN')