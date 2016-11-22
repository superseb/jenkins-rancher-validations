#
class rancher_infra::ci::validation_tests::server(
  Pattern[/^[a-zA-Z0-9_\-]+$/] $instance_name,
  NotUndef                     $ami_id,
  NotUndef                     $instance_type,
  NotUndef                     $subnet,
  Array[NotUndef]              $security_groups,
  NotUndef                     $ssh_key,
  NotUndef                     $tags,
  Enum['present', 'absent']    $ensure = present,
  NotUndef                     $region = $::rancher_infra::ci::validation_tests::region,
  NotUndef                     $zone = $::rancher_infra::ci::validation_tests::zone,
) {

  case $ensure {
    'present': {
      ecs_instance { $instance_name:
        ensure                      => present,
        region                      => $region,
        availability_zone           => "${region}${zone}",
        image_id                    => $ami_id,
        intance_type                => $instance_type,
        associate_public_ip_address => true,
        subnet                      => $subnet,
        security_groups             => $security_groups,
        key_name                    => $ssh_key,
        tags                        => $tags,
      }
    }

    'absent': {
      ecs_instance { $instance_name:
        ensure            => absent,
        region            => $region,
        availability_zone => "${region}${zone}",
      }
    }

    default: { fail("Invalid valued specified for \'${ensure}: ${ensure}.") }
  }
}
