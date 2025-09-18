from apps.authentication.models import Role, User

def run():
    role_map = {1:"superadmin",2:"admin",3:"user1",4:"user2"}
    fixed, skipped = 0, 0
    for u in User.objects.all():
        rid = getattr(u, "role_id", None)
        if isinstance(rid, int):
            role_name = role_map.get(rid)
            if role_name:
                try:
                    role = Role.objects.get(name=role_name)
                    u.role = role
                    u.save(update_fields=["role"])
                    fixed += 1
                except Role.DoesNotExist:
                    print(f"Role '{role_name}' not found for user {u.username}")
                    skipped += 1
            else:
                print(f"No mapping for role_id {rid} (user {u.username})")
                skipped += 1
    print(f"Updated {fixed} users, skipped {skipped}.")
