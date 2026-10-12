"""Oracle 무료 ARM 서버(A1.Flex, 2 OCPU/12GB) 자리가 날 때까지 GitHub Actions 에서 생성 시도.
설정/키는 전부 GitHub Secrets (환경변수) 로 받음. 공개 저장소라 OCID/IP 는 로그에 찍지 않는다.
한 번 실행에 RUN_MINUTES 동안 2분 간격으로 시도. 서버가 생기면 성공 표시 파일(created) 을 만들고 끝.
"""
import os
import time
from pathlib import Path

import oci

E = os.environ
COMPARTMENT = E["OCI_TENANCY"]
SUBNET, IMAGE, AD, SSH_KEY = E["OCI_SUBNET"], E["OCI_IMAGE"], E["OCI_AD"], E["OCI_SSH_KEY"]
DEADLINE = time.time() + float(E.get("RUN_MINUTES", "340")) * 60
INTERVAL = 120


def log(m):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {m}", flush=True)


def existing(cc):
    for i in cc.list_instances(compartment_id=COMPARTMENT).data:
        if i.display_name == "trading" and i.lifecycle_state not in ("TERMINATED", "TERMINATING"):
            return i
    return None


def launch(cc):
    d = oci.core.models.LaunchInstanceDetails(
        availability_domain=AD, compartment_id=COMPARTMENT, display_name="trading", shape="VM.Standard.A1.Flex",
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=2, memory_in_gbs=12),  # Always Free 는 2/12 까지
        source_details=oci.core.models.InstanceSourceViaImageDetails(image_id=IMAGE, boot_volume_size_in_gbs=150,
                                                                     boot_volume_vpus_per_gb=10),
        create_vnic_details=oci.core.models.CreateVnicDetails(subnet_id=SUBNET, assign_public_ip=True),
        metadata={"ssh_authorized_keys": SSH_KEY})
    return cc.launch_instance(d).data


def main():
    cfg = {"user": E["OCI_USER"], "fingerprint": E["OCI_FINGERPRINT"], "tenancy": COMPARTMENT,
           "region": E.get("OCI_REGION", "ap-tokyo-1"), "key_content": E["OCI_KEY"]}
    oci.config.validate_config(cfg)
    cc = oci.core.ComputeClient(cfg)
    n = 0
    while time.time() < DEADLINE:
        inst = existing(cc)
        if inst:
            log(f"서버 있음 ({inst.lifecycle_state}) - 끝. 공인 IP 는 오라클 콘솔에서 확인")
            Path("created").write_text(inst.lifecycle_state)
            return
        n += 1
        try:
            launch(cc)
            log(f"시도 #{n} 생성 성공! (2 OCPU / 12 GB)")
            continue                                   # 다음 바퀴에서 existing() 으로 확인
        except oci.exceptions.ServiceError as e:
            if e.status == 429:
                log(f"시도 #{n} 요청이 너무 잦음 - 5분 쉼")
                time.sleep(300)
                continue
            log(f"시도 #{n} 실패: {e.status} {(e.message or '')[:80]}")
        except Exception as e:
            log(f"시도 #{n} 오류: {type(e).__name__}")
        time.sleep(INTERVAL)
    log(f"이번 실행 시간 끝 ({n}번 시도) - 다음 예약 실행이 이어서 함")


if __name__ == "__main__":
    main()
