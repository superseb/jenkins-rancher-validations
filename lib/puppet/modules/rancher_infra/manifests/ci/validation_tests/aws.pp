#
class rancher_infra::ci::validation_tests::aws(
  Enum['present', 'absent']           $ensure = 'present',
  Pattern[/^[a-z]{2}\-[a-z]+\-\d+$/]  $region = $::rancher_infra::ci::validation_tests::region,
  Pattern[/^[a-e]$/]                  $zone = $::rancher_infra::ci::validation_tests::zone,
  Optional[Hash[String, String]]      $addtl_tags = undef,
  ) {

  $_tags = merge($addtl_tags, $::rancher_infra::ci::validation_tests::default_tags)
  $vpc_cidr_block = '172.16.0.0/16'
  $subnet_cidr_block = '172.16.100.0/24'

  if 'present' == $ensure {

    ec2_vpc { 'ci-validation-tests-vpc':
      ensure           => present,
      cidr_block       => $vpc_cidr_block,
      instance_tenancy => 'default',
      region           => $region,
      tags             => $_tags,
    }

    ec2_vpc_routetable { 'ci-validation-tests-subnet-routing':
      ensure => present,
      region => $region,
      vpc    => 'ci-validation-tests-vpc',
      routes => [
        {
        destination_cidr_block => $vpc_cidr_block,
        gateway                => 'local',
        },
        {
        destination_cidr_block => '0.0.0.0/0',
        gateway                => 'ci-validation-tests-vpc-gateway',
        },
      ],
    }

    ec2_vpc_subnet { 'ci-validation-tests-subnet':
      ensure            => present,
      vpc               => 'ci-validation-tests-vpc',
      region            => $region,
      availability_zone => "${region}${zone}",
      cidr_block        => $subnet_cidr_block,
      route_table       => 'ci-validation-tests-subnet-routing',
      tags              => $_tags,
      } ->

      # WARNING :: Yes, the rules below can be simplified to remove explicit port rules however that results
      # in breakage in docker-machine (09.2016) SSH rules handling. If the rule is specified here then docker-machine
      # will not lose its f-ing mind.
      ec2_securitygroup { 'ci-validation-tests-sg':
        ensure      => present,
        description => 'SG for Rancher CI nodes',
        region      => $region,
        ingress     => [
          {
            security_group => 'ci-validation-tests-sg' },
          {
            security_group => 'ci-validation-tests-sg',
            protocol       => 'tcp',
            port           => '22', },
          {
            security_group => 'ci-validation-tests-sg',
            protocol       => 'tcp',
            port           => '2376', },
          {
            cidr => '0.0.0.0/0',
          },
          {
            protocol => 'tcp',
            cidr     => '0.0.0.0/0',
            port     => '22',
          },
          {
            protocol => 'tcp',
            cidr     => '0.0.0.0/0',
            port     => '2376',
          },
        ],
        vpc         => 'ci-validation-tests-vpc',
        tags        => $_tags,
      }

      ec2_vpc_internet_gateway { 'ci-validation-tests-vpc-gateway':
        ensure => present,
        region => $region,
        vpc    => 'ci-validation-tests-vpc',
      }
  }

  if 'absent' == $ensure {

    ec2_vpc_internet_gateway { 'ci-validation-tests-vpc-gateway':
      ensure => absent,
      region => $region,
    } ->

    ec2_vpc_subnet { 'ci-validation-tests-subnet':
      ensure => absent,
      region => $region,
    } ->

    ec2_vpc_routetable { 'ci-validation-tests-subnet-routing':
      ensure => absent,
      region => $region,
    } ->

    ec2_securitygroup { 'ci-validation-tests-sg':
      ensure => absent,
      region => $region,
    } ->

    ec2_vpc { 'ci-validation-tests-vpc':
      ensure => absent,
      region => $region,
    }
  }
}
