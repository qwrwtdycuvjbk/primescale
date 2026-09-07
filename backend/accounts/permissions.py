from rest_framework.permissions import BasePermission
from .models import User


class IsCandidate(BasePermission):
    """
    Allows access only to authenticated users with the 'candidate' role.
    """
    message = "Only candidates are authorized to access this resource."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.CANDIDATE
        )


class IsEmployer(BasePermission):
    """
    Allows access only to authenticated users with the 'employer' role.
    """
    message = "Only employers are authorized to access this resource."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.EMPLOYER
        )


class IsAdmin(BasePermission):
    """
    Allows access only to authenticated users with the 'admin' role, is_staff, or is_superuser.
    """
    message = "Administrative privileges required to access this resource."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                request.user.role == User.Role.ADMIN
                or request.user.is_staff
                or request.user.is_superuser
            )
        )


class IsCandidateOrAdmin(BasePermission):
    """
    Allows access to candidates or administrative users.
    """
    message = "Candidate or admin privileges required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                request.user.role == User.Role.CANDIDATE
                or request.user.role == User.Role.ADMIN
                or request.user.is_staff
                or request.user.is_superuser
            )
        )


class IsEmployerOrAdmin(BasePermission):
    """
    Allows access to employers or administrative users.
    """
    message = "Employer or admin privileges required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                request.user.role == User.Role.EMPLOYER
                or request.user.role == User.Role.ADMIN
                or request.user.is_staff
                or request.user.is_superuser
            )
        )


class IsOwnerOrAdmin(BasePermission):
    """
    Object-level permission foundation allowing owners of an object (or admins) to read/write it.
    Checks obj.owner, obj.user, obj.posted_by, or obj itself if it is the User instance.
    """
    message = "You do not have permission to access or modify this object."

    def has_object_permission(self, request, view, obj):
        if not (request.user and request.user.is_authenticated):
            return False

        # Admins have full access
        if (
            request.user.role == User.Role.ADMIN
            or request.user.is_staff
            or request.user.is_superuser
        ):
            return True

        # If obj is User itself
        if isinstance(obj, User):
            return obj == request.user

        # If obj has a user relation (e.g. CandidateProfile)
        if hasattr(obj, "user"):
            return obj.user == request.user

        # If obj has an owner relation (e.g. Company)
        if hasattr(obj, "owner"):
            return obj.owner == request.user

        # If obj has a posted_by relation (e.g. Job)
        if hasattr(obj, "posted_by"):
            return obj.posted_by == request.user

        return False
