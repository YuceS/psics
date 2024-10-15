from aws_cdk import SecretValue, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_rds as rds
from constructs import Construct


class SimpleAppStack(Stack):

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # VPC
        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            ip_addresses=ec2.IpAddresses.cidr("192.179.0.0/16"),
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                )
            ],
        )

        # Security Group for RDS
        self.db_security_group = ec2.SecurityGroup(
            self,
            "DbSecurityGroup",
            vpc=self.vpc,
            description="Allow access to DbInstance",
            allow_all_outbound=True,
        )
        self.db_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(), connection=ec2.Port.all_traffic()
        )

        # RDS Subnet Group
        rds_subnet_group = rds.SubnetGroup(
            self,
            "DBSubnetGroup",
            description="DBSubnetGroup",
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        # RDS Instance
        rds.DatabaseInstance(
            self,
            "DbInstance",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16_4
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE2, ec2.InstanceSize.MICRO
            ),
            credentials=rds.Credentials.from_password(
                username="admin", password=SecretValue.unsafe_plain_text("HelL0w0rLD")
            ),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_groups=[self.db_security_group],
            publicly_accessible=True,
            subnet_group=rds_subnet_group,
            database_name="Db",
            allocated_storage=50,
        )

        # Security Group for EC2
        my_ec2_security_group = ec2.SecurityGroup(
            self,
            "Ec2SecurityGroup",
            vpc=self.vpc,
            description="Allow access to Ec2Instance",
            allow_all_outbound=False,
        )
        my_ec2_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(), connection=ec2.Port.tcp(443)
        )
        my_ec2_security_group.add_egress_rule(
            peer=self.db_security_group, connection=ec2.Port.tcp(3306)
        )

        # EC2 Instance
        self.ec2_instance = ec2.Instance(
            self,
            "Ec2Instance",
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE4_GRAVITON, ec2.InstanceSize.MICRO
            ),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=my_ec2_security_group,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/sda1",
                    volume=ec2.BlockDeviceVolume.ebs(
                        8, volume_type=ec2.EbsDeviceVolumeType.GP3
                    ),
                )
            ],
        )

        # IAM Role for EC2 Instance
        self.iam_role = iam.Role(
            self,
            "IamRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
            ],
        )

        # Attach the Role to the EC2 instance
        self.ec2_instance.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
        )
